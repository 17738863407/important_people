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

PAGE_RULE = {'rule_id': '0251',
 'domain': 'www.cma.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_cma_con_list_jgsz_v1',
 'leader_region_selector': 'div.con_list_jgsz',
 'name_selector': 'h5 a',
 'duty_selector': 'h6',
 'detail_link_selector': 'h5 a[href]',
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
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div.con_list_jgsz',
                     'name_selector': 'h5 a',
                     'duty_selector': 'h6',
                     'detail_link_selector': 'h5 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'online_static_html_builder',
                           'verified_status': 'online_pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def is_name_text(value: str) -> bool:
    return bool(re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', clean_text(value)))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    base_url = final_url
    rows = []
    for card in soup.select('div.con_list_jgsz'):
        name_node = card.select_one('h5 a') or card.select_one('h5')
        duty_node = card.select_one('h6')
        name = clean_text(name_node.get_text(' ', strip=True) if name_node else '')
        duty = clean_text(duty_node.get_text(' ', strip=True) if duty_node else '')
        if not is_name_text(name) or not duty:
            continue
        link = card.select_one('h5 a[href]') or card.select_one('a[href]')
        detail_url = urljoin(base_url, link.get('href')) if link and link.get('href') and base_url else ''
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_cma_con_list_jgsz_v1',
            'selector_summary': 'leader=div.con_list_jgsz；name=h5 a；duty=h6；detail=h5 a[href]；api_enabled=False；online_html=True',
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
