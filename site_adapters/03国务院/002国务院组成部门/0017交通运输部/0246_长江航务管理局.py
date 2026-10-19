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
    "rule_id": "0246", "page_type": "人物列表完整页", "structure_group": "cjhy_ldwy_cards_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cjhy_ldwy_cards_v1",
    "leader_region_selector": "ul.ldwy_list li", "name_selector": "span.leader_name", "duty_selector": "span.leader_zw", "detail_link_selector": "a.clearfix[href]",
    "content_scope": {"start_anchor": "领导网页", "end_anchor": "Copyright", "include_selectors": ["ul.ldwy_list"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "static_http", "detail_link_selector": "ul.ldwy_list li a.clearfix[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "必须限定领导网页ldwy_list，排除新闻人物和正文干扰", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_ldwy_cards",
    "locator": {"css": {"leader_region_selector": "ul.ldwy_list li", "name_selector": "span.leader_name", "duty_selector": "span.leader_zw", "detail_link_selector": "a.clearfix[href]"}, "api": {"enabled": False, "reason": "原始HTML领导卡片直接提供姓名、职务与独立详情链接"}, "migration": {"source": "legacy_business_source_and_entry_default_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(page_rule["leader_region_selector"]):
        name_node = card.select_one("span.leader_name")
        duty_node = card.select_one("span.leader_zw")
        link_node = card.select_one("a.clearfix[href]")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link_node.get("href", "")) if link_node else ""
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=ldwy_list；name=leader_name；duty=leader_zw；detail=card_href；order=dom"})
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
