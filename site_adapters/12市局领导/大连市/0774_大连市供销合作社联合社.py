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


PAGE_RULE = {
    "rule_id": "0774",
    "page_type": "人物目录详情页",
    "structure_group": "dalian_government_information_leader_directory",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "dalian_supply_marketing_leader_detail_v1",
    "leader_region_selector": ".introduce_list .zfxxgk_zdgkc",
    "name_selector": '.introduce_list .zfxxgk_zdgkc a[href*="/art/"]',
    "duty_selector": ".wip_art .art_con p:first-of-type",
    "detail_link_selector": '.introduce_list .zfxxgk_zdgkc a[href*="/art/"]',
    "content_scope": {
        "start_anchor": "领导介绍",
        "end_anchor": "机构职能",
        "include_selectors": [".introduce_list .zfxxgk_zdgkc"],
        "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_parse_page_fetch_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": '.introduce_list .zfxxgk_zdgkc a[href*="/art/"]',
        "detail_parser": "dalian_supply_marketing_detail_first_paragraph_v1",
        "detail_name_selector": ".wip_art .htitle",
        "detail_duty_selector": ".wip_art .art_con p:first-of-type",
        "detail_content_selector": ".wip_art .art_con",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页首段为原始现职，第二段以后为主持、负责或分管信息，不得混入职务依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "入口和五个详情页已于2026-08-08逐页在线验证",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".introduce_list .zfxxgk_zdgkc",
            "name_selector": '.introduce_list .zfxxgk_zdgkc a[href*="/art/"]',
            "duty_selector": ".wip_art .art_con p:first-of-type",
            "detail_link_selector": '.introduce_list .zfxxgk_zdgkc a[href*="/art/"]',
            "content_scope": {
                "start_anchor": "领导介绍",
                "end_anchor": "机构职能",
                "include_selectors": [".introduce_list .zfxxgk_zdgkc"],
                "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
            },
        },
        "api": {"enabled": False, "reason": "入口与人物详情页均为稳定静态HTML"},
    },
}


def clean_text(value: str) -> str:
    """压缩网页排版空白，不改变原文语义。"""
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def fetch_detail_html(detail_url: str, timeout: int) -> str:
    """在线读取单个人物详情页。"""
    response = requests.get(
        detail_url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口页顺序读取人物详情页首段现职。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_links: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.introduce_list .zfxxgk_zdgkc；"
        "name=入口人物链接文本；duty=详情.wip_art .art_con首段"
    )
    for anchor in soup.select('.introduce_list .zfxxgk_zdgkc a[href*="/art/"]'):
        list_name = clean_text(anchor.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        if not list_name or not detail_url or detail_url in seen_links:
            continue
        seen_links.add(detail_url)
        duty = ""
        evidence = ""
        try:
            detail_soup = BeautifulSoup(fetch_detail_html(detail_url, timeout=20), "html.parser")
            detail_name_node = detail_soup.select_one(".wip_art .htitle")
            duty_node = detail_soup.select_one(".wip_art .art_con p")
            detail_name = clean_text(detail_name_node.get_text(" ", strip=True)) if detail_name_node else ""
            if detail_name and detail_name != list_name:
                continue
            evidence = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
            duty = evidence.rstrip("。")
        except requests.RequestException:
            pass
        rows.append(
            {
                "name": list_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
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
