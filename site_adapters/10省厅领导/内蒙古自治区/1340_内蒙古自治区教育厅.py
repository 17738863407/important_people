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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.nmg.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "list_to_detail",
        "collector": "static_http",
        "parser": "page_inner_mongolia_education_leader_detail_card_v1",
        "leader_region_selector": "a[href*='/ldjj_25197/']",
        "name_selector": "leader list link text",
        "duty_selector": "#rightDiv_ldjj .ldjj_xq em",
        "detail_link_selector": "a[href*='/ldjj_25197/']",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": True,
            "mode": "list_to_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": "a[href*='/ldjj_25197/']",
            "detail_name_selector": "#rightDiv_ldjj .ldjj_xq span",
            "detail_duty_selector": "#rightDiv_ldjj .ldjj_xq em",
            "detail_content_selector": "#rightDiv_ldjj .ldjj_xq",
            "max_detail_links": 8,
            "candidate_links": [],
        },
        "risk_flag": "fixed_precise_leader_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "a[href*='/ldjj_25197/']",
                "name_selector": "leader list link text",
                "duty_selector": "#rightDiv_ldjj .ldjj_xq em",
                "detail_link_selector": "a[href*='/ldjj_25197/']",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网领导简介列表和详情页均为静态 HTML"},
            "migration": {"source": "legacy_page_rule", "verified_status": "pending", "behavior_changed": True},
        },
    }


def fetch_detail(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def collect_links(soup: BeautifulSoup, base_url: str, max_links: int) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select("a[href*='/ldjj_25197/']"):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, link.get("href", "").strip())
        if not is_name(name) or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        links.append((name, detail_url))
        if len(links) >= max_links:
            break

    return links


def extract_detail(name_hint: str, detail_html: str) -> tuple[str, str] | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    card = soup.select_one("#rightDiv_ldjj .ldjj_xq") or soup.select_one(".ldxl_mobile2_xq")
    if not card:
        return None

    name_node = card.select_one("span")
    duty_node = card.select_one("em")
    name = clean_name(name_node.get_text(" ", strip=True) if name_node else name_hint)
    duty = normalize_space(duty_node.get_text(" ", strip=True) if duty_node else "")
    duty = re.sub(r"[（(]挂职[）)]$", "", duty).strip()
    if not is_name(name) or not duty or len(duty) > 90:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    max_links = int(page_rule.get("detail_strategy", {}).get("max_detail_links") or 8)
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for name_hint, detail_url in collect_links(soup, base_url, max_links):
        try:
            result = extract_detail(name_hint, fetch_detail(detail_url))
        except requests.RequestException:
            continue
        if not result:
            continue
        name, duty = result
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty[:120],
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=a[href*=ldjj_25197]；detail=.ldjj_xq span/em",
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
    rule_id_value = "1340"
    main(rule_id_value)
