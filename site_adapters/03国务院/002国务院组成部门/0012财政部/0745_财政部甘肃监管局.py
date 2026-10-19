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
    "rule_id": "0745",
    "page_type": "领导信息入口页",
    "structure_group": "入口导航到局领导子页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "follow_leader_page",
    "collector": "static_http",
    "parser": "MofGansuLeaderSubpageParser_v2",
    "leader_region_selector": ".liBox li a[href][title]",
    "risk_flag": "权威入口仅含内设机构，须动态跟随局领导导航链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一链接标题中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """从权威入口动态发现局领导子页，再按子页DOM顺序解析。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_soup = BeautifulSoup(html, "html.parser")
    leader_link = next(
        (
            link
            for link in entry_soup.select("a[href]")
            if _clean_text(link.get_text(" ", strip=True)) == "局领导"
        ),
        None,
    )
    if leader_link is None:
        return []

    leader_url = urljoin(base_url, leader_link.get("href", ""))
    fetch_result = fetch_html_with_strategy(leader_url, strategy="requests")
    leader_soup = BeautifulSoup(fetch_result.html, "html.parser")
    detail_base_url = fetch_result.final_url or leader_url
    records: list[dict] = []
    seen: set[str] = set()
    for link in leader_soup.select(rule["leader_region_selector"]):
        card_text = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?(?:局长|组长|巡视员))\s+([\u4e00-\u9fff·]{2,8})", card_text)
        if not match:
            continue
        duty, name = match.groups()
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(detail_base_url, link.get("href", "")),
                "parser": rule["parser"],
                "selector_summary": "入口局领导链接；子页.liBox领导组合标题",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
