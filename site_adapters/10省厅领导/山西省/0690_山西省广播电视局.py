from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0690',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'custom_shanxi_gdj_sidebar_detail_v1',
 'leader_region_selector': 'div.main-listcon-left',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'div.main-listcon-left a[href*="/ldjj"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'div.main-listcon-left a[href*="/ldjj"]',
                     'detail_parser': 'custom_shanxi_gdj_sidebar_detail_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '规则入口本身是首位领导详情页并通过左侧栏链接其他领导；只在.main-listcon-right当前人物区域提取现任句，排除简历与分工',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > head > title',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """规范化页面文本空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def fetch_detail_html(detail_url: str) -> str:
    """读取山西省广播电视局领导详情页 HTML。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    return fetch_by_raw_requests(detail_url, timeout=60).html


def parse_detail_page(html: str, detail_url: str, page_rule: dict) -> dict[str, str] | None:
    """从单个领导详情页抽取姓名和现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".main-listcon-right") or soup
    text = clean_text(content.get_text(" ", strip=True))
    match = re.search(r"(?P<name>[\u4e00-\u9fff]{2,4})，.*?现任(?P<duty>山西省广播电视局.*?)(?:，|。)", text)
    if not match:
        return None
    duty = match.group("duty").strip()
    source_url = str(page_rule.get("url") or "")
    return {
        "organization": str(page_rule.get("organization", "")),
        "url": str(page_rule.get("url", "")),
        "name": match.group("name").strip(),
        "duty": duty,
        "detail_url": "" if detail_url.rstrip("/") == source_url.rstrip("/") else detail_url,
        "evidence": duty,
        "confidence": "high",
        "parser": str(page_rule.get("parser", "")),
        "selector_summary": "detail=div.main-listcon-left a[href*=/ldjj]；content=.main-listcon-right；duty=现任句",
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析山西省广播电视局侧栏领导详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    detail_urls: list[str] = [base_url]
    for link in soup.select('div.main-listcon-left a[href*="/ldjj"]'):
        detail_url = urljoin(base_url, str(link.get("href", "")))
        if detail_url not in detail_urls:
            detail_urls.append(detail_url)
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for detail_url in detail_urls[:50]:
        detail_html = html if detail_url == base_url else fetch_detail_html(detail_url)
        row = parse_detail_page(detail_html, detail_url, page_rule)
        if row is None or row["name"] in seen_names:
            continue
        seen_names.add(row["name"])
        rows.append(row)
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
