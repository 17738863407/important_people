from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """领导链接为空时显式进入人工复核，禁止从其他业务网址猜测入口。"""
    raise RuntimeError("规则主表领导链接为空，未确认真实领导入口，需人工复核")


PAGE_RULE = {
    "rule_id": "4430",
    "page_type": "领导入口缺失显式失败",
    "structure_group": "missing_leader_entry_manual_review",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "manual_review",
    "collector": "raw_http",
    "parser": "page_missing_leader_entry_manual_review_v1",
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "leader_region_selector": "",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "规则主表领导链接为空；不得从官网首页、目录页或新闻报道猜测领导入口",
    "confidence": "manual_review",
    "filter_policy": "strong_no_wordlist",
}


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
