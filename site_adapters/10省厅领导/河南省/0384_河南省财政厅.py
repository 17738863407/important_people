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

PAGE_RULE = {'rule_id': '0384',
 'domain': 'czt.henan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_finance_leader_box_v1',
 'leader_region_selector': '.bsznBox li',
 'name_selector': 'p a',
 'duty_selector': 'span a',
 'detail_link_selector': 'p a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.bsznBox'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'p a[href]',
                     'detail_parser': '',
                     'detail_name_selector': 'p a',
                     'detail_duty_selector': 'span a',
                     'detail_content_selector': '.bsznBox',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.bsznBox li',
                     'name_selector': 'p a',
                     'duty_selector': 'span a',
                     'detail_link_selector': 'p a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.bsznBox'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导卡片直接提供姓名和职务'}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return clean_text(value).rstrip('：:')


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.bsznBox li'):
        name_node = item.select_one('p a')
        duty_node = item.select_one('span a')
        if not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_url = urljoin(final_url, name_node.get('href', ''))
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': '',
            'order': len(rows) + 1,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_henan_finance_leader_box_v1',
            'selector_summary': 'leader=.bsznBox li；name=p a；duty=span a；detail=p a[href]；api_enabled=False',
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
