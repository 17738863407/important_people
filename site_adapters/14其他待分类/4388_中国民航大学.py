from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4388",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "cauc_current_leaders_image",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "force_browser": False,
    "extract_mode": "vision_llm",
    "collector": "raw_http",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#vsb_content_15922_u161 img.img_vsb_content",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#vsb_content_15922_u161"], "exclude_selectors": []},
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "现任领导名单仅由正文图片承载，视觉结果必须回指同次逐字转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "weak_visual_validated",
    "profile_reusable": False,
    "profile_judgement": "已核验正文只有一张现任领导名单图片",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#vsb_content_15922_u161 img.img_vsb_content",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取中国民航大学现任领导名单图片中明确列出的姓名和对应完整职务；同一姓名在党委职务与行政职务等不同栏目重复出现时，每个姓名职务事实分别输出一条记录，每条evidence和visual_span只包含能够逐字回指该项职务的原文片段，后续由页面脚本按姓名合并；严格按图片自上而下、同一行从左到右的版面顺序输出；不得把标题或其他文字识别为人物，不得依据常识、历史名单或旧输出补写；图片没有人物独立详情链接，detail_url必须为空。",
        "evidence_validation": "exact_normalized_substring",
        "tile_edge": 3000,
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """逐项校验视觉事实，并按姓名合并同一人物的多项职务。"""
    from crawler_core.deepseek_vision import call_deepseek_vision_json
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import (
        compact_text,
        download_image_bytes,
        find_target_image_urls,
        prepare_vision_image_tiles,
        resolve_prompt_path,
        validate_visual_rows,
        write_vision_audit,
    )

    project_dir = resolve_project_dir()
    strategy = page_rule["vision_strategy"]
    image_urls = find_target_image_urls(page_rule, html, final_url)
    if len(image_urls) != 1:
        raise RuntimeError(f"现任领导目标图片数量异常：{len(image_urls)}")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 180)
    image_bytes, _ = download_image_bytes(image_urls[0], final_url, timeout_seconds)
    tiles = prepare_vision_image_tiles(
        image_bytes,
        tile_edge=int(strategy.get("tile_edge") or 3000),
    )
    if len(tiles) != 1:
        raise RuntimeError(f"现任领导图片切片数量变化，需重新核验版面：{len(tiles)}")

    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt = (
        f"{prompt_path.read_text(encoding='utf-8')}\n\n"
        f"机构：{compact_text(page_rule.get('organization'))}\n"
        f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
        f"图片序号：1\n图片URL：{image_urls[0]}\n"
        f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
        "当前为全图第1至1块，全图共1块；只处理当前批次实际可见内容。"
    )
    result = call_deepseek_vision_json(
        images=[(tiles[0], "image/png")],
        prompt=prompt,
        project_dir=project_dir,
        timeout_seconds=timeout_seconds,
    )
    transcription = str(result.payload.get("transcription") or "").strip()
    if not transcription:
        raise RuntimeError("DeepSeek视觉JSON缺少transcription逐字转写")

    records: list[object] = []
    for item in result.payload.get("rows") or []:
        records.extend(
            validate_visual_rows(
                page_rule,
                {"rows": [item]},
                transcription,
                transcription,
                image_order_offset=0,
                selector=str(strategy.get("target_image_selector") or ""),
            )
        )
    write_vision_audit(
        project_dir,
        page_rule,
        result,
        prompt_path,
        image_urls[0],
        hashlib.sha256(image_bytes).hexdigest(),
        1,
        1,
        1,
        1,
        transcription,
        len(records),
    )
    if result.payload.get("json_recovered"):
        raise RuntimeError("DeepSeek视觉JSON不完整")
    if not records:
        raise RuntimeError("视觉结果未通过逐项证据校验")

    merged: list[object] = []
    by_name: dict[str, object] = {}
    for record in records:
        current = by_name.get(record.name)
        if current is None:
            by_name[record.name] = record
            merged.append(record)
            continue
        duties = [item for item in current.duty.split("；") if item]
        if record.duty and record.duty not in duties:
            duties.append(record.duty)
            current.duty = "；".join(duties)
    for index, record in enumerate(merged, start=1):
        record.order = str(index)
    return merged


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
