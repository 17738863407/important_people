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
    "rule_id": "4124",
    "page_type": "现任领导正文图片",
    "load_mode": "图片承载",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".TRS_UEDITOR img",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_notes": "现任领导由正文图片承载，必须在线发现图片并校验同次转写，不能以缺少HTML文字判定为空页。",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".TRS_UEDITOR img",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "仅按现任领导图片的行列阅读顺序抽取明确姓名与完整职务，保留所有限定信息，不推断或补全。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, page_url: str, rule: dict) -> list:
    """解析当前正文图片并验证同次模型证据。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    return parse_vision_llm_records(rule, html, page_url, 30)


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
