from __future__ import annotations

import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造排除理事分组后的组织成员图片DeepSeek视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id,
        ".r1-content img[imageid='22151']",
        (
            "抽取整张组织成员图片中明确列出的全部人物，不能只处理带照片和简介的人员；"
            "主席、副主席兼秘书长、驻会副主席、副秘书长、监事、常务理事等"
            "分组属于抽取范围；职务标题为‘理事’的整个人物分组不属于抽取范围；"
            "每个人的raw_duty应采用其所属组织分组的职务标题，不能用照片下方的校外本职简介"
            "替换其在本组织中的职务；唯一例外是‘国际、国内体育、教育组织、机构履职’分类，"
            "该分类不是职务，组内人物应采用各自照片下方明确列出的具体履职；"
            "严格按图片版面从上到下、同一行从左到右输出；"
            "若一个职务标题对应多名人物，每人的evidence和visual_span都必须覆盖该组连续图片转写原文，"
            "raw_duty必须逐字来自evidence中的连续图片文字，跨行合并只能删除排版空白，"
            "严禁在相邻职务行之间新增顿号、逗号、分号或其他字符；"
            "不得把页面导航、栏目名称、图片装饰或旧结果作为人物信息。"
        ),
    )
    page_rule["vision_strategy"]["allow_group_title_context"] = True
    return page_rule


def find_roster_sections(image_bytes: bytes) -> list[tuple[int, int]]:
    """依据贯穿长图的细横线动态划分组织职务分组。"""
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        # 原图透明区域的底色为黑色；检测阶段保留该底色，避免铺白后把大片透明区误判为横线。
        detection_image = image.convert("RGB")
        sample = detection_image.resize((256, detection_image.height)).convert("L")
        pixels = sample.load()
        candidate_rows = [
            y
            for y in range(sample.height)
            if sum(1 for x in range(sample.width) if pixels[x, y] >= 235) / sample.width >= 0.95
        ]

    runs: list[tuple[int, int]] = []
    for row in candidate_rows:
        if not runs or row > runs[-1][1] + 1:
            runs.append((row, row))
        else:
            runs[-1] = (runs[-1][0], row)
    dividers = [
        (start + end) // 2
        for start, end in runs
        if 2 <= end - start + 1 <= 10 and end < detection_image.height - 20
    ]
    if len(dividers) != 6:
        raise RuntimeError(f"2525长图分组线数量异常：期望6条，实际{len(dividers)}条")
    boundaries = [0, *dividers, detection_image.height]
    return [
        (
            max(0, boundaries[index] - 24),
            min(detection_image.height, boundaries[index + 1] + 24),
        )
        for index in range(len(boundaries) - 1)
    ]


def prepare_section_images(image_bytes: bytes, top: int, bottom: int) -> list[bytes]:
    """为单个完整分组生成总览及左右放大图。"""
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        rgba_image = image.convert("RGBA")
        white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
        white_background.alpha_composite(rgba_image)
        section = white_background.convert("RGB").crop((0, top, image.width, bottom))
        images: list[bytes] = []
        overview = section.copy()
        if max(overview.size) > 2200:
            ratio = 2200 / max(overview.size)
            overview = overview.resize(
                (max(1, round(overview.width * ratio)), max(1, round(overview.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        overview_output = BytesIO()
        overview.save(overview_output, format="PNG")
        images.append(overview_output.getvalue())

        if section.width > 1600:
            crop_width = round(section.width * 0.6)
            for left in (0, section.width - crop_width):
                crop = section.crop((left, 0, left + crop_width, section.height))
                crop_output = BytesIO()
                crop.save(crop_output, format="PNG")
                images.append(crop_output.getvalue())
        return images


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """按组织分组切分长图，逐组运行DeepSeek视觉抽取。"""
    from crawler_core.deepseek_vision import call_deepseek_vision_json
    from crawler_core.llm_text import compact_text, resolve_prompt_path
    from crawler_core.llm_vision import download_image_bytes
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import (
        find_target_image_urls,
        validate_visual_rows,
        write_vision_audit,
    )

    project_dir = resolve_project_dir()
    strategy = page_rule["vision_strategy"]
    if not isinstance(strategy, dict):
        raise RuntimeError("2525视觉规则缺少vision_strategy字典")
    image_urls = find_target_image_urls(page_rule, html, final_url)
    if len(image_urls) != 1:
        raise RuntimeError(f"2525目标名单图片数量异常：{len(image_urls)}")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 300)
    image_bytes, _ = download_image_bytes(image_urls[0], final_url, timeout_seconds)
    sections = find_roster_sections(image_bytes)
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    allowed_duties = {
        "主席",
        "副主席兼秘书长",
        "驻会副主席",
        "驻会副主席、副秘书长",
        "副主席",
        "副秘书长",
        "常务理事",
        "理事",
        "监事",
    }
    records: list[object] = []
    seen_names: set[str] = set()
    for section_index, (top, bottom) in enumerate(sections, start=1):
        section_images = prepare_section_images(image_bytes, top, bottom)
        duty_instruction = (
            "当前分组标题是‘国际、国内体育、教育组织、机构履职’，它只是分类标题。"
            "每人的raw_duty必须采用其照片下方明确列出的具体履职。"
            if section_index == 4
            else (
                "必须使用本分组顶部组织职务标题作为raw_duty；若标题由多个组织职务合并组成，"
                "必须依据人物说明中明确写出的本组织职务，为每个人匹配标题中的对应单项职务，"
                "不得把整个组合标题赋给单个人；说明中的‘主席（兼）’对应标题中的‘主席’，"
                "说明中的‘副主席兼秘书长’对应标题中的同名职务。人物照片下方的校外本职或"
                "个人简介仅用于定位姓名，绝对不能作为raw_duty。"
            )
        )
        prompt = (
            f"{prompt_template}\n\n机构：{compact_text(page_rule.get('organization'))}\n"
            f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
            f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
            f"当前为长图第{section_index}/{len(sections)}个完整组织分组。第1张为分组总览，"
            "其余图片是同一分组的左右放大图，只用于复核小字，人物不得重复输出。"
            f"{duty_instruction}"
        )
        result = call_deepseek_vision_json(
            images=[(image, "image/png") for image in section_images],
            prompt=prompt,
            project_dir=project_dir,
            timeout_seconds=timeout_seconds,
        )
        transcription = str(result.payload.get("transcription") or "").strip()
        if not transcription:
            raise RuntimeError(f"DeepSeek视觉JSON缺少逐字转写：分组{section_index}")
        section_records = validate_visual_rows(
            page_rule,
            result.payload,
            transcription,
            transcription,
            image_order_offset=(section_index - 1) * 10000,
            selector=str(strategy.get("target_image_selector") or ""),
        )
        accepted_records = []
        for record in section_records:
            if section_index != 4 and record.duty not in allowed_duties:
                raise RuntimeError(
                    f"分组{section_index}识别到非组织职务：{record.name}={record.duty}"
                )
            if record.duty == "理事":
                continue
            if record.name in seen_names:
                continue
            seen_names.add(record.name)
            accepted_records.append(record)
        audit_path = write_vision_audit(
            project_dir,
            page_rule,
            result,
            prompt_path,
            image_urls[0],
            hashlib.sha256(image_bytes).hexdigest(),
            len(section_images),
            len(section_images),
            section_index,
            len(sections),
            transcription,
            len(accepted_records),
        )
        audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_payload["image_preprocessing"] = (
            f"semantic_section_{section_index}_overview_plus_horizontal_crops"
        )
        audit_payload["section_bounds"] = [top, bottom]
        audit_path.write_text(
            json.dumps(audit_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if result.payload.get("json_recovered"):
            raise RuntimeError(f"DeepSeek视觉JSON不完整：分组{section_index}")
        records.extend(accepted_records)
    for index, record in enumerate(records, start=1):
        record.order = str(index)
    return records


def main(rule_id: str) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "2525"
    main(rule_id_value)
