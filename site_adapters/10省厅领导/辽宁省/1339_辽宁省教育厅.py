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
        "domain": "jyt.ln.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "list_to_detail",
        "collector": "static_http",
        "parser": "page_liaoning_education_leader_detail_current_position_v1",
        "leader_region_selector": ".provincial-leaders-inner dd.ldname a[href]",
        "name_selector": ".provincial-leaders-inner dd.ldname a",
        "duty_selector": ".TRS_Editor text: 现任...。",
        "detail_link_selector": ".provincial-leaders-inner dd.ldname a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": True,
            "mode": "list_to_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".provincial-leaders-inner dd.ldname a[href]",
            "detail_name_selector": "list link text",
            "detail_duty_selector": ".TRS_Editor text: 现任...。",
            "detail_content_selector": ".TRS_Editor",
            "max_detail_links": 10,
            "candidate_links": [],
        },
        "risk_flag": "fixed_precise_current_leader_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".provincial-leaders-inner dd.ldname a[href]",
                "name_selector": ".provincial-leaders-inner dd.ldname a",
                "duty_selector": ".TRS_Editor text: 现任...。",
                "detail_link_selector": ".provincial-leaders-inner dd.ldname a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网部门领导列表及详情页均为静态 HTML"},
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

    for link in soup.select(".provincial-leaders-inner dd.ldname a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, link.get("href", "").strip())
        if not is_name(name) or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        links.append((name, detail_url))
        if len(links) >= max_links:
            break

    return links


def extract_duty(name: str, detail_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".TRS_Editor")
    if not content:
        return "", ""

    text = normalize_space(content.get_text(" ", strip=True))
    match = re.search(r"现任(.+?)[。；;]", text)
    if not match:
        return "", ""

    duty = normalize_space(match.group(1)).rstrip("。；;")
    duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
    if not duty or len(duty) > 80 or name in duty:
        return "", ""
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    max_links = int(page_rule.get("detail_strategy", {}).get("max_detail_links") or 10)
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for name, detail_url in collect_links(soup, base_url, max_links):
        duty, evidence = extract_duty(name, fetch_detail(detail_url))
        if name in seen_names or not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=.provincial-leaders-inner dd.ldname a；detail=.TRS_Editor 现任",
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
    rule_id_value = "1339"
    main(rule_id_value)
