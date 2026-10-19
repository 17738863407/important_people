from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4047",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "force_browser": False,
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#xlmain img[src*='W020250106399659235547.jpg']",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "DeepSeek视觉结果必须逐条回指同次响应的图片逐字转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#xlmain img[src*='W020250106399659235547.jpg']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取现任领导正文图片中明确出现的姓名和当前职务，保持图片版面顺序。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行 DeepSeek 视觉抽取并验证证据。"""
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main() -> None:
    """运行当前图片人物脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
