from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4255",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "民航局空管局局领导图片名单",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "extract_mode": "vision_llm",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": ".jld2_uldiv > img[src*='zzjgleadNew']",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物姓名与职务只存在于官网图片，须由视觉转写逐条回指。",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".jld2_uldiv > img[src*='zzjgleadNew']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取局领导图片中明确列出的现任人员姓名和对应职务，按图片从上到下、从左到右的阅读顺序输出；不得抽取栏目标题或推断缺失信息。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """执行视觉转写、结构化抽取及来源图片证据校验。"""
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    rows = parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        get_settings().browser_timeout_seconds,
    )
    for row in rows:
        evidence = re.sub(rf"[：:、,，\-—\s]*{re.escape(row.name)}$", "", row.evidence).strip()
        row.duty = evidence
        row.evidence = evidence
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
