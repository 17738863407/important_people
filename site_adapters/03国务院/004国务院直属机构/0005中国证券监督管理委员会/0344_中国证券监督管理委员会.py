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

PAGE_RULE = {'rule_id': '0344',
 'domain': 'www.csrc.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_list_csrc_sidebar_detail_profile_v1',
 'leader_region_selector': 'ul.sidebar a[href]',
 'name_selector': '侧栏“职务：姓名”冒号后',
 'duty_selector': '侧栏“职务：姓名”冒号前',
 'detail_link_selector': 'ul.sidebar a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': '',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '列表页侧栏已直接包含姓名和职务，无需详情页解析',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.sidebar a[href]',
                     'name_selector': '侧栏“职务：姓名”冒号后',
                     'duty_selector': '侧栏“职务：姓名”冒号前',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '列表页侧栏已直接包含姓名和职务，无需详情页解析'},
             'migration': {'source': 'online_detail_chain_builder',
                           'verified_status': 'online_pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', value or '').strip()


def is_name_text(value: str) -> bool:
    return bool(re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', clean_name(value)))


def parse_sidebar_label(value: str) -> tuple[str, str]:
    text = clean_text(value)
    if '：' not in text:
        return '', ''
    duty, name = text.split('：', 1)
    return clean_name(name), clean_text(duty)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for link in soup.select('ul.sidebar a[href]'):
        label = clean_text(link.get_text(' ', strip=True))
        name, fallback_duty = parse_sidebar_label(label)
        if not is_name_text(name) or name in seen:
            continue
        duty = fallback_duty
        if not is_name_text(name) or not duty:
            continue
        seen.add(name)
        resolved_detail_url = urljoin(final_url, link.get('href')) if final_url else ''
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': resolved_detail_url if resolved_detail_url != final_url else '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_list_csrc_sidebar_detail_profile_v1',
            'selector_summary': 'leader=ul.sidebar a[href]；name=侧栏冒号后；duty=侧栏冒号前；detail=none；api_enabled=False',
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
