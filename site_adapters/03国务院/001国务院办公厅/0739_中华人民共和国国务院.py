from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0739", "page_type": "人物列表完整页", "structure_group": "gov_state_council_leader_table_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_gov_state_council_leader_table_v2",
    "leader_region_selector": ".content.gwy.gwyzzjg table tr", "name_selector": "td a[href]", "duty_selector": "td.pcShow", "detail_link_selector": "td a[href]",
    "content_scope": {"start_anchor": "国务院领导", "end_anchor": "国务院组织机构", "include_selectors": [".content.gwy.gwyzzjg table"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": ".content.gwy.gwyzzjg table tr td a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "同一人物可在不同职务行重复出现；按网页每个链接出现顺序输出并保留各自原始职务节点，不拼接职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_state_council_table_rows",
    "locator": {"css": {"leader_region_selector": ".content.gwy.gwyzzjg table tr", "name_selector": "td a[href]", "duty_selector": "td.pcShow", "detail_link_selector": "td a[href]"}, "api": {"enabled": False, "reason": "原始HTML国务院领导表格直接提供职务、姓名与独立详情链接"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table_row in soup.select(page_rule["leader_region_selector"]):
        duty_node = table_row.select_one("td.pcShow")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").replace(" ", "")
        if not duty:
            continue
        for link_node in table_row.select("td a[href]"):
            name = clean_text(link_node.get("title") or link_node.get_text(" ", strip=True))
            name = re.sub(r"[（(]兼[）)]$", "", name).replace(" ", "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
                continue
            rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link_node.get("href", "")), "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=state_council_table；duty=td.pcShow；name_and_detail=td_a；order=row_then_link"})
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
