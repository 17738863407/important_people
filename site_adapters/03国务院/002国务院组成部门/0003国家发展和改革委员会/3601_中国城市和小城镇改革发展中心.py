from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3601", "domain": "www.ccud.org.cn", "page_type": "领导列表卡片",
    "structure_group": "ccud_leader_cards_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "card_name_duty_detail",
    "collector": "static_http", "parser": "page_ccud_leaders_v1", "leader_region_selector": "ul.leader",
    "name_selector": ".leaderTit", "duty_selector": ".leaderInfor p", "detail_link_selector": "li > a[href]",
    "detail_strategy": {"required": False, "mode": "direct_card_link", "candidate_links": []},
    "risk_flag": "exclude_biography_and_recommendations", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """清理排版空白和职务展示引导符。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("—- ：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名、职务和人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul.leader")
    if region is None:
        response = requests.get(
            str(page_rule.get("url", "")),
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        final_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")
        region = soup.select_one("ul.leader")
    if region is None: return []
    rows: list[dict[str, str]] = []
    for item in region.select(":scope > li"):
        link, name_node, duty_node = item.select_one(":scope > a[href]"), item.select_one(".leaderTit"), item.select_one(".leaderInfor p")
        if link is None or name_node is None or duty_node is None: continue
        name, duty = clean(name_node.get_text(" ", strip=True)), clean(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty: continue
        rows.append({"name": name, "duty": duty, "evidence": duty,
                     "detail_url": urljoin(final_url, str(link.get("href", ""))), "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "strategy=custom_parse_page；region=ul.leader；item=>li；fields=.leaderTit+.leaderInfor p+>a"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
