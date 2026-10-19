from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2031",
    "page_type": "人物目录详情页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "official_home_to_leader_cards",
    "parser": "page_parse_page",
    "leader_region_selector": ".leaders",
    "name_selector": ".leaders .leader-item p.txt:first-of-type",
    "duty_selector": ".leaders .leader-item p.txt:nth-of-type(2)",
    "detail_link_selector": ".leaders .leader-item > a[href]",
    "detail_strategy": {"required": True, "mode": "official_home_to_current_leader_directory"},
    "risk_flag": "规则入口是分工通知归档；现行姓名职务位于同站政务公开首页动态链接的领导卡片目录",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "先从同站政务公开首页的领导信息模块发现现行目录，再按卡片DOM顺序提取姓名、职务和详情页。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从同站政务公开首页发现现行领导目录并解析强结构卡片。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    public_home_url = urljoin(final_url, "../../../")
    public_home_result = fetch_by_raw_requests(public_home_url)
    public_home_soup = BeautifulSoup(public_home_result.html, "html.parser")
    directory_link = next(
        (
            link
            for link in public_home_soup.select(".zwgk-leader a[href]")
            if re.sub(r"\s+", "", link.get_text(" ", strip=True)) == "领导信息"
        ),
        None,
    )
    if directory_link is None:
        raise ValueError("同站政务公开首页未发现领导信息目录链接")

    directory_url = urljoin(public_home_result.final_url, str(directory_link.get("href", "")))
    directory_result = fetch_by_raw_requests(directory_url)
    directory_soup = BeautifulSoup(directory_result.html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in directory_soup.select(".leaders .leader-item > a[href]"):
        text_nodes = card.select("p.txt")
        if len(text_nodes) < 2:
            continue
        name = re.sub(r"\s+", "", text_nodes[0].get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", text_nodes[1].get_text(" ", strip=True)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(directory_result.final_url, str(card.get("href", ""))),
                "evidence": duty,
                "parser": "page_parse_page",
                "selector_summary": "政务公开首页=.zwgk-leader；现行目录=.leaders .leader-item卡片",
            }
        )
    if not rows:
        raise ValueError("现行领导目录未发现具有姓名和职务两行的卡片")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
