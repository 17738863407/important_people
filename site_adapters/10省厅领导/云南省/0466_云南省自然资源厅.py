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

PAGE_RULE = {
    'rule_id': '0466',
    'domain': 'dnr.yn.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_yunnan_dnr_ldzl_cards_v1',
    'leader_region_selector': '.zfxxgk_ldzc_content .ldzl-content',
    'name_selector': '.zfxxgk_ldzc_content .ld-name a',
    'duty_selector': '.zfxxgk_ldzc_content .ld-duty',
    'detail_link_selector': '.zfxxgk_ldzc_content .ld-name a[href]',
    'content_scope': {
        'start_anchor': '领导之窗',
        'end_anchor': '',
        'include_selectors': ['.zfxxgk_ldzc_content'],
        'exclude_selectors': [],
    },
    'detail_strategy': {
        'required': False,
        'mode': 'none',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '.zfxxgk_ldzc_content .ld-name a[href]',
        'detail_parser': '',
        'detail_name_selector': '',
        'detail_duty_selector': '',
        'detail_content_selector': '',
        'max_detail_links': 50,
        'candidate_links': [],
    },
    'risk_flag': '页面包含iframe',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '.zfxxgk_ldzc_content .ldzl-content',
            'name_selector': '.zfxxgk_ldzc_content .ld-name a',
            'duty_selector': '.zfxxgk_ldzc_content .ld-duty',
            'detail_link_selector': '.zfxxgk_ldzc_content .ld-name a[href]',
            'content_scope': {
                'start_anchor': '领导之窗',
                'end_anchor': '',
                'include_selectors': ['.zfxxgk_ldzc_content'],
                'exclude_selectors': [],
            },
        },
        'api': {'enabled': False, 'reason': '在线静态页面已包含完整领导姓名和职务'},
        'migration': {
            'source': 'sequential_static_html_builder',
            'verified_status': 'verified_online_direct',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ').replace('\u2003', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for card in soup.select('.zfxxgk_ldzc_content .ldzl-content'):
        link = card.select_one('.ld-name a[href]')
        duty_node = card.select_one('.ld-duty')
        if not link or not duty_node:
            continue
        name = clean_name(link.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True)).strip('。')
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
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
            'parser': 'page_inline_yunnan_dnr_ldzl_cards_v1',
            'selector_summary': 'leader=.zfxxgk_ldzc_content .ldzl-content；name=.ld-name a；duty=.ld-duty；detail=.ld-name a[href]；api_enabled=False',
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
