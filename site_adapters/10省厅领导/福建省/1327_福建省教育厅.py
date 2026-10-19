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


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.fujian.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_to_detail",
        "collector": "static_http",
        "parser": "page_fujian_education_leader_list_detail_xianren_v1",
        "leader_region_selector": ".leader_area",
        "name_selector": ".leader_name_list a[href]",
        "duty_selector": ".leader_content p 现任句",
        "detail_link_selector": ".leader_name_list a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {
            "required": True,
            "mode": "list_to_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".leader_name_list a[href]",
            "detail_name_selector": ".leader_content p 人名逗号前",
            "detail_duty_selector": ".leader_content p 现任句",
            "detail_content_selector": ".leader_content",
            "max_detail_links": 6,
        },
        "risk_flag": "精确领导详情链",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".leader_area",
                "name_selector": ".leader_name_list a[href]",
                "duty_selector": ".leader_content p 现任句",
                "detail_link_selector": ".leader_name_list a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网领导详情页为静态 HTML"},
        },
    }


def extract_name_duty(text: str) -> tuple[str, str, str] | None:
    value = normalize_space(text)
    match = re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff])?)\s*[，,].*?现任(.+?)。", value)
    if not match:
        return None
    name = clean_name(match.group(1))
    duty = normalize_space(match.group(2))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    evidence = duty
    return name, duty, evidence


def fetch_detail(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_detail(detail_html: str) -> tuple[str, str, str] | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select(".leader_content p"):
        result = extract_name_duty(paragraph.get_text(" ", strip=True))
        if result:
            return result
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()

    for link in soup.select(".leader_name_list a[href]")[:6]:
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("#", "javascript:")):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        try:
            result = parse_detail(fetch_detail(detail_url))
        except requests.RequestException:
            continue
        if not result:
            continue
        name, duty, evidence = result
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "" if detail_url.rstrip("/") == base_url.rstrip("/") else detail_url,
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=.leader_name_list a；detail=.leader_content p 现任句",
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
    rule_id_value = "1327"
    main(rule_id_value)
