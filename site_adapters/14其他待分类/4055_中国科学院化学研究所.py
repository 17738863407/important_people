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
    "rule_id": "4055",
    "page_type": "研究所领导卡片页",
    "structure_group": "cas_leader_card_link_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cas_leader_card_v1",
    "leader_region_selector": "现任领导正文 .row 内 a[target=_blank]",
    "name_selector": "a > h5",
    "duty_selector": "a > p",
    "detail_link_selector": "a[href$='.html']",
    "content_scope": {
        "start_anchor": "当前位置： 首页 现任领导",
        "end_anchor": "版权所有",
        "include_selectors": ["a[target=_blank]:has(h5):has(p)"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "响应同时含桌面与移动版卡片，仅采用h5+p的桌面卡片以避免重复。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验现任领导区6张姓名—职务—独立详情链接卡片。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "a[target=_blank]:has(h5):has(p)"}, "api": {"enabled": False, "reason": "HTML卡片完整"}, "migration": {"verified_status": "verified"}},
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("a[target=_blank]:has(h5):has(p)"):
        name = card.find("h5").get_text(" ", strip=True)
        duty = card.find("p").get_text(" ", strip=True)
        href = card.get("href", "")
        if not (2 <= len(name) <= 4 and name.isalpha() and duty):
            continue
        detail_url = "" if not href.endswith(".html") else urljoin(final_url, href)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "现任领导桌面卡片a>h5+p"})
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
