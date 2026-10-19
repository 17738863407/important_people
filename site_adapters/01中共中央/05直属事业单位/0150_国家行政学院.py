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
    "rule_id": "0150", "page_type": "多人物详情合并页", "structure_group": "ccps_current_leader_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ccps_current_leader_cards_v1",
    "leader_region_selector": "div.xrld-list div.item", "name_selector": "p.name", "duty_selector": "p.zw, p.longzw", "detail_link_selector": "a[href]",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "Copyright", "include_selectors": ["div.xrld-list"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": "div.xrld-list div.item a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "必须限定现任领导xrld-list，排除站内新闻人物与其他正文", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_current_leader_cards",
    "locator": {"css": {"leader_region_selector": "div.xrld-list div.item", "name_selector": "p.name", "duty_selector": "p.zw, p.longzw", "detail_link_selector": "a[href]"}, "api": {"enabled": False, "reason": "原始HTML现任领导卡片直接提供强字段与人物详情链接"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        name_node = item.select_one("p.name")
        duty_node = item.select_one("p.zw, p.longzw")
        link_node = item.select_one("a[href]")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link_node.get("href", "")) if link_node else ""
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=xrld-list；name=p.name；duty=p.zw,p.longzw；detail=card_href；order=dom"})
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
