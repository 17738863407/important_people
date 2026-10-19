from __future__ import annotations

import re
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
    "rule_id": "4216", "page_type": "中心概况内的领导子页", "load_mode": "静态 HTML 直出",
    "extract_mode": "list_direct", "parser": "page_inline_ncc_leaders_v1",
    "leader_region_selector": "中心领导子页的现任领导块", "name_selector": "职务行冒号后姓名",
    "duty_selector": "职务行冒号前文本", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http", "confidence": "high", "filter_policy": "strong_content_boundary",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从入口页动态发现“中心领导”子页，再解析“现任领导”至联系方式的职务行。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    entry_url = str(page_rule["url"])
    if not html:
        html = fetch_by_raw_requests(entry_url).html
    entry_soup = BeautifulSoup(html, "html.parser")
    leader_link = next(
        (anchor.get("href") for anchor in entry_soup.select("a[href]") if anchor.get_text(" ", strip=True) == "中心领导"),
        "",
    )
    if not leader_link:
        return []
    leader_url = urljoin(final_url or entry_url, leader_link)
    texts = list(BeautifulSoup(fetch_by_raw_requests(leader_url).html, "html.parser").stripped_strings)
    start = next(i for i, text in enumerate(texts) if text == "现任领导")
    end = next(i for i in range(start + 1, len(texts)) if texts[i].startswith("电话"))
    rows: list[dict] = []
    for text in texts[start + 1 : end]:
        compact = "".join(text.split())
        match = re.fullmatch(r"(.+?)：([\u4e00-\u9fff]{2,4})", compact)
        if match:
            duty, name = match.groups()
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
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
