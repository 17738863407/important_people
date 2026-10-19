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
        "domain": "jyt.shaanxi.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_to_single_detail",
        "collector": "static_http",
        "parser": "page_shaanxi_education_single_detail_all_cards_v1",
        "leader_region_selector": ".ldgl a[href]",
        "name_selector": ".w-leader-cont-right .cont-detail[id]",
        "duty_selector": ".w-leader-cont-right .cont-detail[id] first p",
        "detail_link_selector": ".ldgl a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": True,
            "mode": "list_to_single_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".ldgl a[href]",
            "detail_name_selector": ".cont-detail[id]",
            "detail_duty_selector": ".cont-detail[id] first p",
            "detail_content_selector": ".w-leader-cont-right",
            "max_detail_links": 1,
            "candidate_links": [],
        },
        "risk_flag": "fixed_single_detail_all_leaders",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".ldgl a[href]",
                "name_selector": ".cont-detail[id]",
                "duty_selector": ".cont-detail[id] first p",
                "detail_link_selector": ".ldgl a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网详情页静态 HTML 一次包含全部领导卡片"},
            "migration": {"source": "legacy_page_rule", "verified_status": "pending", "behavior_changed": True},
        },
    }


PAGE_RULE = build_page_rule(
    "1343",
    
)


def fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def collect_first_detail_url(soup: BeautifulSoup, base_url: str) -> str:
    for link in soup.select(".ldgl a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if is_name(name):
            return urljoin(base_url, link.get("href", "").strip())
    return ""


def extract_duty(name: str, card: BeautifulSoup) -> str:
    first_para = card.select_one("p")
    text = normalize_space(first_para.get_text(" ", strip=True) if first_para else card.get_text(" ", strip=True))
    if text.startswith(name):
        text = normalize_space(text[len(name) :])
    duty = re.split(
        r"，(?:中共党员|群众|民盟|民进|农工党|博士|硕士|大学|本科学历|博士研究生|硕士研究生)|。",
        text,
        maxsplit=1,
    )[0]
    return normalize_space(duty).strip("，。")


def parse_detail(detail_html: str, detail_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(detail_html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for card in soup.select(".w-leader-cont-right .cont-detail[id]"):
        name = clean_name(card.get("id", ""))
        duty = extract_duty(name, card)
        if name in seen_names or not is_name(name) or not duty or len(duty) > 90:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；detail_once=.w-leader-cont-right .cont-detail[id]；duty=first p prefix",
                "order": str(len(rows) + 1),
            }
        )

    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url
    detail_url = collect_first_detail_url(soup, base_url)
    if not detail_url:
        return []
    return parse_detail(fetch_html(detail_url), detail_url.split("#", 1)[0], page_rule)


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
