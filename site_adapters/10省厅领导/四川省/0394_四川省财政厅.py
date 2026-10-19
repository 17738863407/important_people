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

PAGE_RULE = {'rule_id': '0394',
 'domain': 'czt.sc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_list_sichuan_finance_detail_current_sentence_v1',
 'leader_region_selector': '.gknr_list ul.ldfg.clearfix li',
 'name_selector': 'a[title]',
 'duty_selector': '详情页“现任”句',
 'detail_link_selector': 'a[href][title]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.gknr_list ul.ldfg.clearfix'],
                   'exclude_selectors': ['ul.zsdw']},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href][title]',
                     'detail_parser': 'detail_current_position_before_division_v1',
                     'detail_name_selector': 'h1',
                     'detail_duty_selector': '现任 至 句号/分工',
                     'detail_content_selector': 'body',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+detail',
 'locator': {'css': {'leader_region_selector': '.gknr_list ul.ldfg.clearfix li',
                     'name_selector': 'a[title]',
                     'duty_selector': '详情页“现任”句',
                     'detail_link_selector': 'a[href][title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.gknr_list ul.ldfg.clearfix'],
                                       'exclude_selectors': ['ul.zsdw']}},
             'api': {'enabled': False, 'reason': '姓名来自列表页，职务来自静态详情页'}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\u2002', ' ').replace('\u2003', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:。])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def fetch_detail_duty(url: str) -> str:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    text = clean_text(BeautifulSoup(response.text, 'lxml').get_text(' ', strip=True))
    match = re.search(r'现任(?P<duty>.+?)(?:。|分工[:：])', text)
    if not match:
        return ''
    return clean_text(match.group('duty')).strip('。')


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.gknr_list ul.ldfg.clearfix li'):
        link = item.select_one('a[href][title]')
        if not link:
            continue
        name = clean_name(link.get('title') or link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        duty = fetch_detail_duty(detail_url)
        if not duty:
            continue
        duty = re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])', '', duty)
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': '',
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_list_sichuan_finance_detail_current_sentence_v1',
            'selector_summary': 'leader=.gknr_list ul.ldfg.clearfix li；name=a[title]；duty=detail 现任句；detail=a[href][title]；api_enabled=False',
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
