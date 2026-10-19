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
    "rule_id": "2162",
    "page_type": "人物表格页",
    "structure_group": "qingdao_gov_ldxx_table_v1",
    "reuse_scope": "qingdao_government_ldxx_pages",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "S012_qingdao_gov_ldxx_table_v1",
    "leader_region_selector": "table#table5",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "同页后续包含内设机构信息；仅解析带有职务与个人简历标签的table5领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list:
    """沿用青岛政务网注册解析器，直接使用已分离职务字段作为依据说明。"""
    from crawler_core.parser_registry import parse_with_registered_parser

    rows = parse_with_registered_parser(page_rule, html, final_url, None)
    for row in rows:
        row.evidence = str(row.duty or "").strip()
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
