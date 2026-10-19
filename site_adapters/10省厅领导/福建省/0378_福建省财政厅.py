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

PAGE_RULE = {'rule_id': '0378',
 'domain': 'czt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_fujian_finance_leader_dropdown_v1',
 'leader_region_selector': '.leader_name_list .dropdown_menu li',
 'name_selector': 'a[href] span',
 'duty_selector': 'a[href] p',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.leader_name_list .dropdown_menu'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': '',
                     'detail_name_selector': 'a[href] span',
                     'detail_duty_selector': 'a[href] p',
                     'detail_content_selector': '.leader_name_list .dropdown_menu',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leader_name_list .dropdown_menu li',
                     'name_selector': 'a[href] span',
                     'duty_selector': 'a[href] p',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.leader_name_list .dropdown_menu'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线左侧领导下拉列表已直出姓名和职务'}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.leader_name_list .dropdown_menu li'):
        link = item.select_one('a[href]')
        name_node = item.select_one('a[href] span')
        duty_node = item.select_one('a[href] p')
        if not link or not name_node or not duty_node:
            continue
        name = clean_text(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        source_url = final_url or page_rule['url']
        href = str(link.get('href') or '').strip()
        detail_url = ''
        if href and not href.lower().startswith(('#', 'javascript:')):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip('/') != source_url.rstrip('/'):
                detail_url = candidate_url
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_fujian_finance_leader_dropdown_v1',
            'selector_summary': 'leader=.leader_name_list .dropdown_menu li；name=a[href] span；duty=a[href] p；detail=a[href]；api_enabled=False',
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
