from __future__ import annotations

import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容site_adapters下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含crawler_core的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造领导信息图片的DeepSeek视觉证据解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector="img[alt^='图片']",
        instruction=(
            "页面正文按DOM顺序包含多张领导信息图片；逐图只抽取图片中明确出现的姓名和完整当前职务，"
            "保持图片顺序。不得依据历史名单、机构常识或其他图片补写；姓名位于简历行、职务位于职务行时，"
            "每条evidence和visual_span必须逐字重复从职务行开始、经过中间分工行、到包含姓名的简历行结束的"
            "完整连续图片转写原文块，不得跳过分工行或拼接不连续片段。raw_duty只能取职务行，分工、人口学"
            "简历和联系方式不得作为当前职务。"
        ),
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """整体放大横向领导图后运行DeepSeek视觉解析，避免职务行被切断。"""
    from PIL import Image

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
        raise RuntimeError("2696视觉规则缺少vision_strategy字典")
    image_urls = find_target_image_urls(page_rule, html, final_url)
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 180)
    records: list[object] = []
    seen_names: set[str] = set()
    for image_index, image_url in enumerate(image_urls, start=1):
        image_bytes, _ = download_image_bytes(image_url, final_url, timeout_seconds)
        with Image.open(BytesIO(image_bytes)) as image:
            rgba_image = image.convert("RGBA")
            white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
            white_background.alpha_composite(rgba_image)
            rgb_image = white_background.convert("RGB")
            enlarged = rgb_image.resize(
                (rgb_image.width * 2, rgb_image.height * 2),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            enlarged.save(output, format="PNG")
            prepared_image = output.getvalue()
        prompt = (
            f"{prompt_template}\n\n机构：{compact_text(page_rule.get('organization'))}\n"
            f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
            f"图片序号：{image_index}\n图片URL：{image_url}\n"
            f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
            "当前视觉输入是完整横向图片的2倍放大图，必须完整读取职务行，不得在中途截断。"
        )
        result = call_deepseek_vision_json(
            images=[(prepared_image, "image/png")],
            prompt=prompt,
            project_dir=project_dir,
            timeout_seconds=timeout_seconds,
        )
        transcription = str(result.payload.get("transcription") or "").strip()
        if not transcription:
            raise RuntimeError(f"DeepSeek视觉JSON缺少逐字转写：图片{image_index}")
        image_records = validate_visual_rows(
            page_rule,
            result.payload,
            transcription,
            transcription,
            image_order_offset=(image_index - 1) * 10000,
            selector=str(strategy.get("target_image_selector") or ""),
        )
        accepted_records = []
        for record in image_records:
            if record.name in seen_names:
                continue
            seen_names.add(record.name)
            accepted_records.append(record)
        audit_path = write_vision_audit(
            project_dir,
            page_rule,
            result,
            prompt_path,
            image_url,
            hashlib.sha256(image_bytes).hexdigest(),
            1,
            1,
            1,
            1,
            transcription,
            len(accepted_records),
        )
        audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_payload["image_preprocessing"] = "full_horizontal_image_lanczos_2x"
        audit_path.write_text(
            json.dumps(audit_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if result.payload.get("json_recovered"):
            raise RuntimeError(f"DeepSeek视觉JSON不完整：图片{image_index}")
        records.extend(accepted_records)
    for index, record in enumerate(records, start=1):
        record.order = str(index)
    return records


def main(rule_id: str) -> None:
    """运行当前图片人物脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "2696"
    main(rule_id_value)
