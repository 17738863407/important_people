from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '1706',
 'domain': 'www.mva.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'mva_leader_list_online_detail_duties_v1',
 'leader_region_selector': '.overview-left ul.first',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.overview-left ul.first',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def fetch_detail_duty(detail_url: str) -> tuple[str, str]:
    """在线进入人物页，并从详情正文第二段读取网页原始职务。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "Referer": detail_url,
    }
    response = requests.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    article_url = response.url
    redirect_match = re.search(r"location\.replace\([\"']([^\"']+)[\"']\)", response.text)
    if redirect_match:
        article_url = urljoin(response.url, redirect_match.group(1))
        headers["Referer"] = response.url
        response = requests.get(article_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
    paragraphs = BeautifulSoup(response.text, "html.parser").select(".view p, .trs_editor_view p")
    duty = paragraphs[1].get_text(" ", strip=True) if len(paragraphs) > 1 else ""
    duty = re.sub(r"\s+", "", duty)
    duty = re.sub(r"[（(]兼[）)]", "", duty)
    return duty, article_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析领导介绍列表，职务实时来自人物详情页。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    base_url = final_url or str(page_rule.get("url", ""))
    for link in soup.select(".overview-left ul.first a[href]"):
        name = link.get_text(" ", strip=True)
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        if not name or "/ldjs/ldjj/" not in detail_url:
            continue
        try:
            duty, detail_url = fetch_detail_duty(detail_url)
        except requests.RequestException:
            continue
        if not duty:
            continue
        rows.append(
            PersonRecord(
                organization=str(page_rule.get("organization", "")),
                url=str(page_rule.get("url", "")),
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser="mva_leader_list_online_detail_duties_v1",
                selector_summary="leader=.overview-left ul.first a; duty=在线详情.view p第二段",
            )
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
