from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '2802',
 'domain': 'tyjr.xizang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_xizang_veterans_leader_detail_v1',
 'leader_region_selector': 'div.ldzc-nav-l',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'div.ldzc-nav-l',
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


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip(" ：，。;；")


def _detail_duty(detail_url: str, name: str) -> str:
    response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    text = _clean_text(soup.get_text("", strip=True))
    start = text.rfind(f"个人简历{name}")
    if start < 0:
        start = text.rfind(name)
    block = text[start:] if start >= 0 else text
    match = re.search(r"西藏自治区退役军人事务厅([^工作分]+)", block)
    return _clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select("div.ldzc-nav-l a[href]"):
        node = link.select_one("span.name")
        if not node:
            continue
        name = _clean_text(node.get_text(" ", strip=True))
        detail_url = urljoin(final_url, link["href"])
        try:
            duty = _detail_duty(detail_url, name)
        except requests.RequestException:
            continue
        if not name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "" if detail_url.rstrip("/") == final_url.rstrip("/") else detail_url,
                "evidence": f"{name} 西藏自治区退役军人事务厅{duty}",
                "parser": "custom_xizang_veterans_leader_detail_v1",
                "selector_summary": "领导之窗姓名链接+详情规范化职务",
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
