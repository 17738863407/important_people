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

PAGE_RULE = {'rule_id': '2806',
 'domain': 'tyjrsw.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_liaoning_veterans_list_detail_v1',
 'leader_region_selector': 'ul.provincial-leaders-inner',
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
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_page_parser',
 'locator': {'css': {'leader_region_selector': 'ul.provincial-leaders-inner',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'online_static_detail_pages',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ：，。;；")


def _detail_duty(name: str, detail_url: str) -> str:
    try:
        response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    match = re.search(rf"{re.escape(name)}\s+辽宁省退役军人事务厅([^ ]+)", text)
    return _clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict] = []
    for link in soup.select("ul.provincial-leaders-inner dd a[href]"):
        name = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url or source_url, link["href"])
        duty = _detail_duty(name, detail_url)
        if not name or not duty:
            continue
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": f"辽宁省退役军人事务厅{duty}",
                "parser": "custom_liaoning_veterans_list_detail_v1",
                "selector_summary": "部门领导姓名链接+详情机构职务短句",
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
