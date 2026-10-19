from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0388',
 'domain': 'czt.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jiangsu_finance_leader_table_v1',
 'leader_region_selector': 'table.ldzc-list tr',
 'name_selector': '.ldzc-list-left a',
 'duty_selector': '.ldzc-list-right',
 'detail_link_selector': '.ldzc-list-left a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['table.ldzc-list'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.ldzc-list-left a[href]',
                     'detail_parser': '',
                     'detail_name_selector': '.ldzc-list-left a',
                     'detail_duty_selector': '.ldzc-list-right',
                     'detail_content_selector': 'table.ldzc-list',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'table.ldzc-list tr',
                     'name_selector': '.ldzc-list-left a',
                     'duty_selector': '.ldzc-list-right',
                     'detail_link_selector': '.ldzc-list-left a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['table.ldzc-list'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线表格直出姓名、职务和人物页链接'}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('table.ldzc-list tr'):
        name_node = item.select_one('.ldzc-list-left a')
        duty_node = item.select_one('.ldzc-list-right')
        if not name_node or not duty_node:
            continue
        name = clean_text(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_url = urljoin(final_url or page_rule['url'], name_node.get('href', ''))
        same_host = urlparse(detail_url).netloc.lower() == urlparse(final_url).netloc.lower()
        real_person_page = bool(re.search(r'/col/col\d+/index\.html$', urlparse(detail_url).path))
        if not (same_host and real_person_page):
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'organization': page_rule['organization'],
            'url': page_rule['url'],
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_jiangsu_finance_leader_table_v1',
            'selector_summary': 'leader=table.ldzc-list tr；name=.ldzc-list-left a；duty=.ldzc-list-right；detail=.ldzc-list-left a[href]；api_enabled=False',
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
