from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面多张领导图片的DeepSeek视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id,
        ".text img[src^='/uploads/admin/image/']",
        (
            "页面正文按DOM顺序包含多张现任领导图片；逐图只抽取图片中明确出现的姓名和完整当前职务，"
            "保持图片顺序。不得依据历史名单、机构常识或其他图片补写。"
        ),
        fetch_mode="raw_http",
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """按页面图片顺序运行DeepSeek视觉抽取，并清理模型自行补入的分号。"""
    from crawler_core.deepseek_vision import call_deepseek_vision_json
    from crawler_core.llm_text import compact_text, resolve_prompt_path
    from crawler_core.llm_vision import download_image_bytes
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import (
        find_target_image_urls,
        normalize_visual_evidence,
        prepare_vision_image_tiles,
        validate_visual_rows,
        write_vision_audit,
    )

    project_dir = resolve_project_dir()
    strategy = page_rule["vision_strategy"]
    if not isinstance(strategy, dict):
        raise RuntimeError("2693视觉规则缺少vision_strategy字典")
    image_urls = find_target_image_urls(page_rule, html, final_url)
    if not image_urls:
        raise RuntimeError("2693未定位到当前领导图片")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 180)
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    records: list[object] = []
    seen_names: set[str] = set()
    for image_index, image_url in enumerate(image_urls, start=1):
        image_bytes, _ = download_image_bytes(image_url, final_url, timeout_seconds)
        image_tiles = prepare_vision_image_tiles(image_bytes)
        prompt = (
            f"{prompt_template}\n\n"
            f"机构：{compact_text(page_rule.get('organization'))}\n"
            f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
            f"图片序号：{image_index}/{len(image_urls)}\n图片URL：{image_url}\n"
            f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
            "同一人物的多行职务必须只删除排版换行后连接，禁止在原图没有标点的位置新增分号。"
        )
        result = call_deepseek_vision_json(
            images=[(image, "image/png") for image in image_tiles],
            prompt=prompt,
            project_dir=project_dir,
            timeout_seconds=timeout_seconds,
        )
        transcription = str(result.payload.get("transcription") or "").strip()
        if not transcription:
            raise RuntimeError(f"DeepSeek视觉JSON缺少transcription逐字转写：图片{image_index}")
        raw_rows = result.payload.get("rows")
        if not isinstance(raw_rows, list):
            raise RuntimeError(f"DeepSeek视觉JSON缺少rows数组：图片{image_index}")
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            duty = compact_text(item.get("raw_duty") or item.get("duty"))
            evidence = normalize_visual_evidence(item.get("evidence"))
            candidate = duty.replace("；", "").replace(";", "")
            if candidate != duty and normalize_visual_evidence(candidate) in evidence:
                item["raw_duty"] = candidate
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
        write_vision_audit(
            project_dir,
            page_rule,
            result,
            prompt_path,
            image_url,
            hashlib.sha256(image_bytes).hexdigest(),
            len(image_tiles),
            len(image_tiles),
            image_index,
            len(image_urls),
            transcription,
            len(accepted_records),
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
    rule_id_value = "2693"
    main(rule_id_value)
