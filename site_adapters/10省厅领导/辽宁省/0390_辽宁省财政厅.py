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

PAGE_RULE = {'rule_id': '0390',
 'domain': 'czt.ln.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_list_liaoning_finance_detail_css_v1',
 'leader_region_selector': '.oflow-hd li',
 'name_selector': '.ldname a',
 'duty_selector': '详情页 .xxgk_ldlzw a',
 'detail_link_selector': '.ldname a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.oflow-hd'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.ldname a[href]',
                     'detail_parser': 'detail_liaoning_finance_name_duty_css_v1',
                     'detail_name_selector': '.xxgk_ldlxm a',
                     'detail_duty_selector': '.xxgk_ldlzw a',
                     'detail_content_selector': '.main_contRight',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+detail',
 'locator': {'css': {'leader_region_selector': '.oflow-hd li',
                     'name_selector': '.ldname a',
                     'duty_selector': '详情页 .xxgk_ldlzw a',
                     'detail_link_selector': '.ldname a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.oflow-hd'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '姓名来自静态列表，职务在静态详情页中'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, 'lxml')
    name_node = soup.select_one('.xxgk_ldlxm a')
    duty_node = soup.select_one('.xxgk_ldlzw a')
    name = clean_name(name_node.get_text(' ', strip=True)) if name_node else ''
    duty = clean_text(duty_node.get_text(' ', strip=True)) if duty_node else ''
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.oflow-hd li'):
        link = item.select_one('.ldname a[href]')
        if not link:
            continue
        list_name = clean_name(link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', list_name):
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        detail_name, duty = fetch_detail(detail_url)
        name = detail_name or list_name
        if not duty:
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_list_liaoning_finance_detail_css_v1',
            'selector_summary': 'leader=.oflow-hd li；name=.ldname a；duty=detail .xxgk_ldlzw a；detail=.ldname a[href]；api_enabled=False',
        })
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
