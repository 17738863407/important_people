from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4217", "page_type": "分页领导卡片页", "load_mode": "静态 HTML 直出",
    "extract_mode": "card_list", "parser": "page_inline_cams_leaders_v1",
    "leader_region_selector": ".fyxrldlb", "name_selector": ".fyldname", "duty_selector": ".fyldzw",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "inline_parser_handles_fetch": True, "inline_fetch_collector": "raw_http",
    "confidence": "high", "filter_policy": "strong_card_structure",
}


def _parse_cards(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    rows: list[dict] = []
    for card in BeautifulSoup(html, "html.parser").select(".fyxrldlbri"):
        name_node = card.select_one(".fyldname")
        duty_node = card.select_one(".fyldzw")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从当前分页导航动态发现全部领导卡片页，严格按页码与卡片原顺序汇总。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    entry_url = str(page_rule["url"])
    if not html:
        html = fetch_by_raw_requests(entry_url).html
    soup = BeautifulSoup(html, "html.parser")
    page_urls = [final_url or entry_url]
    for anchor in soup.select("a[href]"):
        label = anchor.get_text(" ", strip=True)
        href = anchor.get("href") or ""
        if label.isdigit() and href.endswith(".html"):
            candidate = urljoin(final_url or entry_url, href)
            if candidate not in page_urls:
                page_urls.append(candidate)
    rows: list[dict] = []
    for index, page_url in enumerate(page_urls):
        page_html = html if index == 0 else fetch_by_raw_requests(page_url).html
        rows.extend(_parse_cards(page_html))
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
