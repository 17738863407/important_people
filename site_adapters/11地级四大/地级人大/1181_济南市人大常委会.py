from __future__ import annotations

import hashlib
import json
import re
import sys
from io import BytesIO
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1181",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "playwright",
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#content img[src]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["#content img[src]"],
        "exclude_selectors": [],
    },
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "DeepSeek视觉结果必须逐条回指图片转写原文；仅精确排除职务为“委员”的末尾普通成员，保留其他领导职务",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#content img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": (
            "只抽取目标名单图片中明确出现的姓名及当前职务，按图片版面阅读顺序输出。"
            "名单中的分组职务标题适用于其后全部姓名，直到下一个职务标题或图片结束；"
            "副主任名单横向延伸时必须读取完整一行，不得在中间分块处提前停止；"
            "应把领导分组内每个图片可确认的完整姓名分别输出。不得输出职务标题精确为‘委员’"
            "的末尾普通成员分组；主任、主任委员、副主任、副主任委员、秘书长等领导必须保留；"
            "不得依据历史结果或常识补全图片中无法确认的姓名。"
        ),
        "evidence_validation": "exact_normalized_substring",
        "allow_group_title_context": True,
    },
}


def prepare_roster_images(image_bytes: bytes) -> list[bytes]:
    """生成一张完整总览和三张横向放大图，兼顾分组上下文与小字清晰度。"""
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        rgba_image = image.convert("RGBA")
        white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
        white_background.alpha_composite(rgba_image)
        rgb_image = white_background.convert("RGB")

        prepared_images: list[bytes] = []
        overview_output = BytesIO()
        rgb_image.save(overview_output, format="PNG")
        prepared_images.append(overview_output.getvalue())

        crop_width = min(800, rgb_image.width)
        crop_lefts = [
            0,
            max(0, (rgb_image.width - crop_width) // 2),
            max(0, rgb_image.width - crop_width),
        ]
        for left in dict.fromkeys(crop_lefts):
            crop = rgb_image.crop((left, 0, left + crop_width, rgb_image.height))
            enlarged = crop.resize(
                (crop.width * 2, crop.height * 2),
                Image.Resampling.LANCZOS,
            )
            crop_output = BytesIO()
            enlarged.save(crop_output, format="PNG")
            prepared_images.append(crop_output.getvalue())
        return prepared_images


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """以整图总览加横向放大图运行DeepSeek，并排除末尾普通委员分组。"""
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
        raise RuntimeError("1181视觉规则缺少vision_strategy字典")
    image_urls = find_target_image_urls(page_rule, html, final_url)
    if len(image_urls) != 1:
        raise RuntimeError(f"1181目标名单图片数量异常：{len(image_urls)}")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 180)
    image_bytes, _ = download_image_bytes(image_urls[0], final_url, timeout_seconds)
    prepared_images = prepare_roster_images(image_bytes)
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt = (
        f"{prompt_path.read_text(encoding='utf-8')}\n\n"
        f"机构：{compact_text(page_rule.get('organization'))}\n"
        f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
        f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
        "视觉输入说明：第1张图片是完整名单总览，第2至第4张依次是同一名单的左、中、右放大图。"
        "放大图只用于核对小字，必须依据总览中的相同纵向位置恢复横向分组，所有人物只输出一次。"
    )
    result = call_deepseek_vision_json(
        images=[(image, "image/png") for image in prepared_images],
        prompt=prompt,
        project_dir=project_dir,
        timeout_seconds=timeout_seconds,
    )
    transcription = str(result.payload.get("transcription") or "").strip()
    if not transcription:
        raise RuntimeError("DeepSeek视觉JSON缺少transcription逐字转写")
    records = validate_visual_rows(
        page_rule,
        result.payload,
        transcription,
        transcription,
        image_order_offset=0,
        selector=str(strategy.get("target_image_selector") or ""),
    )
    audit_path = write_vision_audit(
        project_dir,
        page_rule,
        result,
        prompt_path,
        image_urls[0],
        hashlib.sha256(image_bytes).hexdigest(),
        len(prepared_images),
        len(prepared_images),
        1,
        1,
        transcription,
        len(records),
    )
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_payload["image_preprocessing"] = "full_overview_plus_three_horizontal_crops_lanczos_2x"
    audit_path.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if result.payload.get("json_recovered"):
        raise RuntimeError("DeepSeek视觉JSON不完整")

    records = [record for record in records if record.duty.strip() != "委员"]
    if not records:
        raise RuntimeError("排除末尾普通委员分组后未保留任何领导记录")
    for index, record in enumerate(records, start=1):
        record.order = str(index)
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
