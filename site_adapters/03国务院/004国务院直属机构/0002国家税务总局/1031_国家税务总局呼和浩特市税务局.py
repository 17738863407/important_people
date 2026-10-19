from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1031",
    "page_type": "人物列表完整页",
    "structure_group": "政务公开目录XHR领导HTML片段",
    "reuse_scope": "single_page",
    "load_mode": "动态XHR返回HTML片段",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "xhr_html",
    "parser": "HuhhotTaxLeaderXhrFragmentParser_v2",
    "leader_region_selector": ".leaderList",
    "name_selector": "li p:last-of-type",
    "duty_selector": "li p:first-of-type",
    "detail_link_selector": "li a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "入口页通过当前cid对应data-url加载HTML片段；片段内人物链接为独立简介页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """动态发现当前目录XHR片段，再按领导列表DOM顺序抽取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    query = parse_qs(urlsplit(str(rule.get("url", ""))).query)
    channel_id = (query.get("cid") or [""])[0]
    menu_link = soup.select_one(f'a[cid="{channel_id}"][data-url]') if channel_id else None
    fragment_href = menu_link.get("data-url", "") if menu_link else ""
    if not fragment_href:
        raise RuntimeError("未从入口页发现当前cid对应的XHR片段地址")

    fragment_url = urljoin(base_url or str(rule.get("url", "")), fragment_href)
    from crawler_core.fetcher import fetch_by_raw_requests

    fragment_result = fetch_by_raw_requests(fragment_url)
    fragment_soup = BeautifulSoup(fragment_result.html, "html.parser")
    links = fragment_soup.select(".leaderList li a[href]")
    if not links:
        raise RuntimeError("XHR片段未找到领导列表 .leaderList li a[href]")

    rows: list[dict] = []
    seen: set[str] = set()
    for link in links:
        paragraphs = link.select("p")
        if len(paragraphs) < 2:
            continue
        duty = _clean_text(paragraphs[0].get_text(" ", strip=True))
        name = re.sub(r"\s+", "", _clean_text(paragraphs[-1].get_text(" ", strip=True)))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(fragment_result.final_url or fragment_url, link.get("href", "")),
                "parser": PAGE_RULE["parser"],
                "selector_summary": "入口cid对应data-url；.leaderList li a[href]；p首尾字段",
            }
        )

    if not rows:
        raise RuntimeError("XHR领导列表未解析到姓名职务记录")
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
