from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从入口动态发现领导信息栏目，再解析当前领导卡片。"""
    entry = BeautifulSoup(html, "html.parser")
    column_link = entry.select_one("a[href*='/xxgk/0100/0103/']")
    if not column_link:
        return []
    column_url = urljoin(final_url, str(column_link.get("href") or ""))
    response = requests.get(column_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    cards = [*soup.select(".gkpd-ld a[href]"), *soup.select(".gkpd-ldd > ul > li > a[href]")]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, card in enumerate(cards, start=1):
        name_node, duty_node = card.select_one("em"), card.select_one("span")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty,
                     "detail_url": urljoin(response.url, str(card.get("href") or "")),
                     "source_order": str(source_order), "confidence": "high",
                     "parser": "page_inline_hainan_stats_entry_to_leaders_v2"})
    return rows


PAGE_RULE = {
    "rule_id": "2540", "page_type": "人物列表完整页", "structure_group": "海南统计局入口转领导栏目卡片",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_hainan_stats_entry_to_leaders_v2",
    "leader_region_selector": "a[href*='/xxgk/0100/0103/']", "name_selector": "em", "duty_selector": "span",
    "detail_link_selector": ".gkpd-ld a[href], .gkpd-ldd > ul > li > a[href]",
    "detail_strategy": {"required": False, "mode": "discovered_column_card_link", "detail_collector_type": "requests"},
    "risk_flag": "规则入口为首页，必须从当前首页动态发现领导信息栏目，不使用本地存档或固定人物结果",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
