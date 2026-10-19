from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0233",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "vision_llm",
    "collector": "auto",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#detailContent img[src*='2049427752092266498']",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#detailContent img[src*='2049427752092266498']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "DeepSeek视觉结果必须逐条回指同次响应的图片逐字转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "custom_parse_page",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#detailContent img[src*='2049427752092266498']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "按图片原始版面顺序抽取现任领导姓名及其对应职务；标题和届次说明不作为人物。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """调用DeepSeek V4 Flash视觉模型抽取图片并校验证据。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    return parse_vision_llm_records(
        rule=page_rule,
        html=html,
        final_url=final_url,
        timeout_seconds=get_settings().browser_timeout_seconds,
    )


def main() -> None:
    """运行当前DeepSeek图片视觉抽取脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), project_dir / "outputs")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
