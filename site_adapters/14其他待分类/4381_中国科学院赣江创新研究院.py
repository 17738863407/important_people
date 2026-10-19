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
    "rule_id": "4381",
    "page_type": "研究院现任领导卡片页",
    "structure_group": "gia_current_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_gia_current_leaders_v1",
    "leader_region_selector": "ul#content.temp02-wrap-list-img",
    "name_selector": "figure.temp02-content-people h5",
    "duty_selector": "figure.temp02-content-people h5",
    "detail_link_selector": "figure.temp02-content-people a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul#content.temp02-wrap-list-img"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "页头下拉菜单有领导摘要副本，限定正文content卡片列表",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验正文卡片标题、顺序和详情链接",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "ul#content.temp02-wrap-list-img", "name_selector": "figure.temp02-content-people h5", "duty_selector": "figure.temp02-content-people h5", "detail_link_selector": "figure.temp02-content-people a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul#content.temp02-wrap-list-img"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "现任领导卡片直接呈现在HTML中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2002\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("ul#content.temp02-wrap-list-img")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in root.select(":scope > li figure.temp02-content-people"):
        link = card.select_one("a[href]")
        title = card.select_one("h5")
        if link is None or title is None:
            continue
        match = re.match(r"^([\u3400-\u9fff·]{2,5})\s+(.+)$", clean_text(title.get_text(" ", strip=True)))
        if match is None:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")), "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": "ul#content现任领导卡片h5"})
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
