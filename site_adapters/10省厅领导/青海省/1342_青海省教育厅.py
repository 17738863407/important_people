from __future__ import annotations

import re
import sys
from pathlib import Path

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
        "domain": "jyt.qinghai.gov.cn",
        "page_type": "人物接口页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "api_direct",
        "collector": "static_http",
        "parser": "api_qinghai_education_ldzc_index_ashx_v1",
        "leader_region_selector": "#idul li",
        "name_selector": "index.ashx row col[1]",
        "duty_selector": "index.ashx row col[2]",
        "detail_link_selector": "",
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
            "candidate_links": [],
        },
        "risk_flag": "fixed_api_direct_no_detail_chain",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#idul li",
                "name_selector": "index.ashx row col[1]",
                "duty_selector": "index.ashx row col[2]",
                "detail_link_selector": "",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": True, "reason": "领导之窗页面通过 index.js POST index.ashx 加载结构化领导数据"},
            "migration": {"source": "manual_missing_adapter", "verified_status": "pending", "behavior_changed": True},
        },
    }


def fetch_api_rows(api_url: str, referer_url: str) -> list[tuple[str, str, str]]:
    response = requests.post(
        api_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer_url},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding

    rows: list[tuple[str, str, str]] = []
    for raw_row in response.text.split("rrooww"):
        columns = raw_row.split("ccooll")
        if len(columns) < 4:
            continue
        name = clean_name(columns[1])
        duty = normalize_space(columns[2])
        division = normalize_space(columns[3])
        if is_name(name) and duty and len(duty) <= 90:
            rows.append((name, duty, division))
    return rows


def parse_online_html_fallback(html: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, str]] = []
    for item in soup.select("#idul li"):
        name_node = item.select_one("strong")
        spans = [normalize_space(span.get_text(" ", strip=True)) for span in item.select("span")]
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = ""
        division = ""
        for text in spans:
            if text.startswith("职务："):
                duty = normalize_space(text.removeprefix("职务："))
            elif text.startswith("分工："):
                division = normalize_space(text.removeprefix("分工："))
        if is_name(name) and duty and len(duty) <= 90:
            rows.append((name, duty, division))
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    source_url = str(page_rule.get("url", "")) or final_url
    api_url = "https://jyt.qinghai.gov.cn/jg/ldzc/index.ashx"
    try:
        raw_rows = fetch_api_rows(api_url, source_url)
    except requests.RequestException:
        raw_rows = parse_online_html_fallback(html)

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for name, duty, division in raw_rows:
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；api=/jg/ldzc/index.ashx；cols=name/duty/division",
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
    rule_id_value = "1342"
    main(rule_id_value)
