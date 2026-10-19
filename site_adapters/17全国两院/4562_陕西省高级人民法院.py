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
    "rule_id": "4562",
    "page_type": "领导链接缺失",
    "structure_group": "shaanxi_high_court_missing_url_v1",
    "reuse_scope": "missing_url_only",
    "load_mode": "无入口",
    "extract_mode": "custom",
    "parser": "page_shaanxi_high_court_missing_url_v1",
    "leader_region_selector": "",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "规则主表未提供领导链接；禁止猜测入口或人物名单。入口补齐后，领导区域内委员、专职委员同样采集。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """主表入口为空时明确失败，拒绝猜测入口或人物。"""
    raise RuntimeError("规则主表未提供领导链接")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
