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
    "rule_id": "4087",
    "page_type": "现任领导正文图片",
    "load_mode": "图片承载",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "#content .TRS_UEDITOR img",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导姓名职务承载在正文图片，不能将缺少文本误判为空栏目；同次识别证据必须回指图片逐字转写。",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#content .TRS_UEDITOR img",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只读取现任领导正文图片中的姓名和完整现职，按从上到下、同排从左到右的版面顺序，不推断或补写。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """从本次在线页面动态发现正文图片并校验同次视觉证据。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    return parse_vision_llm_records(page_rule, html, final_url, 30)


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
