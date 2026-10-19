from __future__ import annotations

import sys
from pathlib import Path


PAGE_RULE = {
    "rule_id": "1308",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#ContentRegion img[src*='领导班子及分工']",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物姓名职务仅由领导班子图片表格承载，须经DeepSeek视觉解析并回指图片转写原文",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True, "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#ContentRegion img[src*='领导班子及分工']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt", "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取领导班子图片表格中明确出现的姓名及当前职务，按图片表格版面顺序输出。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings
    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
