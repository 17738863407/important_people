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
    "rule_id": "2950",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "V008_text_name_nextline_duty_v1",
    "leader_region_selector": ".neroBox .laye",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_parser": "V008_text_name_nextline_duty_v1",
        "detail_content_selector": ".neroBox .user-picture p",
        "max_detail_links": 10,
    },
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导导航顺序抓取各人物页，并排除等于最终入口页的详情链接。"""
    from crawler_core.detail_links import parse_detail_chain_records
    from crawler_core.settings import get_settings

    rows = parse_detail_chain_records(
        page_rule,
        html,
        final_url,
        None,
        get_settings().request_timeout_seconds,
    )
    normalized_final_url = final_url.rstrip("/")
    for row in rows:
        if row.name and row.duty:
            row.evidence = row.duty
        if row.detail_url.rstrip("/") == normalized_final_url:
            row.detail_url = ""
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
