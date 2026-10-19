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
    "rule_id": "4383",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "csu_current_leaders_image",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "force_browser": False,
    "extract_mode": "vision_llm",
    "collector": "raw_http",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": ".trs_editor_view > p img[data-needdownload='true']",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "规则入口页标题属于空间应用工程与技术中心，必须先验证目标部门归属再进行视觉抽取",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "weak_visual_validated",
    "profile_reusable": False,
    "profile_judgement": "已核验正文只有一张现任领导名单图片",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".trs_editor_view > p img[data-needdownload='true']",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取图片中明确列出的现任领导姓名和对应完整职务，严格按图片自上而下、同一行从左到右的版面顺序输出；不得把标题、机构名或联系方式识别为人物，不得依据常识、历史名单或旧输出补写；图片没有人物独立详情链接，detail_url必须为空。",
        "evidence_validation": "exact_normalized_substring",
        "tile_edge": 3000,
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """执行DeepSeek视觉转写、结构化抽取和证据回指校验。"""
    if "空间科学与应用总体部" not in html and "载人航天工程运行与管理支持中心" not in html:
        raise RuntimeError("入口页归属不符：页面为中国科学院空间应用工程与技术中心现任领导，未出现目标部门名称")
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    return parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        max(get_settings().browser_timeout_seconds, 180),
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
