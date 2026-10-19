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
    "rule_id": "1193",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "playwright",
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": ".article-main img[src]",
    "content_scope": {
        "include_selectors": [".article-main img[src]"],
        "exclude_selectors": [],
    },
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "单张长图承载主席会议成员分组，DeepSeek视觉结果必须逐条回指图片转写原文",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".article-main img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": (
            "只抽取目标长图中明确列出的政协主席会议成员姓名及当前职务，按图片从上到下、从左到右顺序输出。"
            "主席、副主席、秘书长等分组标题适用于其后姓名，直到下一个分组标题或图片结束。"
            "同一分组第二名及以后人物的evidence和visual_span必须完整包含从分组标题开始、经过前序姓名、"
            "直到当前姓名为止的连续图片转写跨度，不得省略中间姓名。"
            "二字姓名若因排版字距被转写为相邻单字，只能按同一分组同一版面块的相邻关系合并；"
            "不得依据历史名单、常识或机构惯例补全任何姓名或职务。"
        ),
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """运行DeepSeek视觉抽取，并执行图片转写证据回指。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    return parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        get_settings().browser_timeout_seconds,
    )


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
