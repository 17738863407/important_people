from __future__ import annotations

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
    "rule_id": "4056", "page_type": "研究所领导卡片页", "structure_group": "cas_caption_leader_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_cas_caption_leader_v1",
    "leader_region_selector": "div.caption:has(h4.media-heading):has(p)", "name_selector": "h4.media-heading > a", "duty_selector": "p", "detail_link_selector": "h4.media-heading > a[href$='.html']",
    "content_scope": {"start_anchor": "领导班子成员", "end_anchor": "机构设置", "include_selectors": ["div.caption:has(h4.media-heading):has(p)"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "card_link"}, "risk_flag": "页面为静态领导卡片，限定caption避免导航链接。", "confidence": "high", "profile_reusable": False,
    "profile_judgement": "已核验6张姓名、职务和独立详情链接卡片。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "div.caption:has(h4.media-heading):has(p)"}, "api": {"enabled": False, "reason": "HTML卡片完整"}, "migration": {"verified_status": "verified"}},
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("div.caption:has(h4.media-heading):has(p)"):
        link = card.select_one("h4.media-heading > a[href]")
        duty_node = card.find("p")
        if link is None or duty_node is None:
            continue
        name, duty = link.get_text(" ", strip=True), duty_node.get_text(" ", strip=True)
        if 2 <= len(name) <= 4 and name.isalpha() and duty:
            rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"]), "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "领导班子caption卡片"})
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
