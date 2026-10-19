from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2633',
 'domain': 'swt.sc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_sichuan_commerce_online_details_v1',
 'leader_region_selector': '领导简介链接及在线详情页',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href*="/sccom/tld"]',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'body',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href*="/sccom/tld"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _extract_detail_duty(detail_html: str, name: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    marker = "当前位置： 首页 > 领导简介"
    if marker in text:
        text = text.split(marker, 1)[1]
    match = re.search(rf"^(?P<duty>.+?)\s+{re.escape(name)}\s+{re.escape(name)}[，,]", text)
    if match:
        return _clean_text(match.group("duty"))
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    title_match = re.search(rf"{re.escape(name)}\s*(?P<duty>[^-]+?)\s*-", title)
    return _clean_text(title_match.group("duty")) if title_match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/sccom/tld"]'):
        name = _normalize_name(link.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(final_url, link.get("href") or "")
        try:
            response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
        except requests.RequestException:
            continue
        duty = _extract_detail_duty(response.text, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_sichuan_commerce_online_details_v1",
                "selector_summary": "领导简介链接+在线详情页职务",
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
