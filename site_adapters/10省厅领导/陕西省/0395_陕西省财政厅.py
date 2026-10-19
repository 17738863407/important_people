from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0395',
 'domain': 'czt.shaanxi.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shaanxi_finance_leader_cards_v1',
 'leader_region_selector': '.leader-section .leader',
 'name_selector': '.text_60',
 'duty_selector': '.text_61',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.leader-section'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '.text_60',
                     'detail_duty_selector': '.text_61',
                     'detail_content_selector': '.leader-section',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.leader-section .leader',
                     'name_selector': '.text_60',
                     'duty_selector': '.text_61',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.leader-section'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导卡片直出姓名和职务'}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.leader-section .leader'):
        name_node = item.select_one('.text_60')
        duty_node = item.select_one('.text_61')
        if not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': '',
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_shaanxi_finance_leader_cards_v1',
            'selector_summary': 'leader=.leader-section .leader；name=.text_60；duty=.text_61；api_enabled=False',
            'order': str(len(rows) + 1),
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
