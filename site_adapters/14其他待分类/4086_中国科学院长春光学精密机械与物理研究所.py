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
    "rule_id": "4086",
    "page_type": "领导卡片页",
    "structure_group": "ciomp_leader_name_span_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "V001_css_field_pair_v1",
    "leader_region_selector": "ul#content",
    "name_selector": "li .leader-name",
    "duty_selector": "li > a > span",
    "risk_flag": "卡片仅含 javascript 链接，不输出详情页链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict):
    """复用强结构卡片解析，并将依据说明收紧为原始职务字段。"""
    from crawler_core.parsers_v1 import parse_strong_css_fields_v1

    rows = parse_strong_css_fields_v1(page_rule, html, final_url)
    for row in rows:
        row.evidence = str(row.duty or "").strip()
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
