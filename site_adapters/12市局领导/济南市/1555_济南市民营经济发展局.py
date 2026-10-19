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
    "rule_id": "1555",
    "page_type": "人物表格页",
    "structure_group": "jinan_label_value_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "V002_table_label_value_v1",
    "leader_region_selector": "div#zoom > div > table",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "人物区域包含简历和工作分工，V002仅接受姓名及职务标签行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """复用V002表格解析结果，仅让依据说明使用已分离的职务字段。"""
    from crawler_core.parsers_v1 import table_label_value_parser_v1

    records = table_label_value_parser_v1(page_rule, html, final_url)
    for record in records:
        record.evidence = record.duty
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
