from __future__ import annotations

import html
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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.ah.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "collector": "static_http",
        "parser": "page_anhui_education_official_js_leader_cards_v1",
        "leader_region_selector": ".wtld li",
        "name_selector": ".wtld li .ind_tit",
        "duty_selector": ".wtld li .ind_info",
        "detail_link_selector": ".wtld li .ind_more a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": None,
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
        },
        "risk_flag": "官方 JS 列表卡片",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".wtld li",
                "name_selector": ".wtld li .ind_tit",
                "duty_selector": ".wtld li .ind_info",
                "detail_link_selector": ".wtld li .ind_more a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": True, "reason": "当前首页 HTML 由官方 JS 列表源注入领导卡片"},
        },
    }


def fetch_official_js_cards() -> str:
    js_url = "https://jyt.ah.gov.cn/ljgl/sylj/wtld/31401661.js?num=100"
    response = requests.get(js_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://jyt.ah.gov.cn/wtld/index.html"}, timeout=20)
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="ignore")
    fragments = re.findall(r"var\s+linkLi\s*=\s*'(.+?)';\s*linkLiArr\.push", text, flags=re.S)
    return "\n".join(html.unescape(fragment) for fragment in fragments)


def collect_cards(soup: BeautifulSoup) -> list[BeautifulSoup]:
    cards = soup.select(".wtld li")
    if cards:
        return cards
    injected_html = fetch_official_js_cards()
    return BeautifulSoup(injected_html, "html.parser").select("li")


def parse_page(html_text: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in collect_cards(soup):
        name_node = card.select_one(".ind_tit")
        duty_node = card.select_one(".ind_info")
        link_node = card.select_one(".ind_more a[href]")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = normalize_space(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        href = str(link_node.get("href") or "").strip() if link_node else ""
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(base_url, href)
            if candidate_url.rstrip("/") != base_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.wtld li/official_js；name=.ind_tit；duty=.ind_info",
            }
        )

    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1326"
    main(rule_id_value)
