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

PAGE_RULE = {'rule_id': '0381',
 'domain': 'czt.guizhou.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_list_guizhou_finance_profile_detail_v1',
 'leader_region_selector': '.ldzc_right li',
 'name_selector': 'a[title]',
 'duty_selector': '详情页“现任/挂职任”句',
 'detail_link_selector': 'a[href][title]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.ldzc_right'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href][title]',
                     'detail_parser': 'detail_current_position_sentence_v1',
                     'detail_name_selector': '列表 title',
                     'detail_duty_selector': '现任/挂职任 至 句号',
                     'detail_content_selector': 'body',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+detail',
 'locator': {'css': {'leader_region_selector': '.ldzc_right li',
                     'name_selector': 'a[title]',
                     'duty_selector': '详情页“现任/挂职任”句',
                     'detail_link_selector': 'a[href][title]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.ldzc_right'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线列表给出详情链接，职务在静态详情页中'}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def fetch_detail_duty(url: str) -> tuple[str, str]:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return '', ''
    response.encoding = response.apparent_encoding or response.encoding
    text = clean_text(BeautifulSoup(response.text, 'lxml').get_text(' ', strip=True))
    match = re.search(r'((?:现任|挂职任)[^。]*。)', text)
    if not match:
        return '', text
    evidence = re.sub(r'^(?:现任|挂职任)\s*', '', clean_text(match.group(1)))
    evidence = re.sub(
        r'[<＜〈(（]\s*(?:挂职|兼|主持日常工作)\s*[>＞〉)）]',
        '',
        evidence,
    ).removesuffix('。').strip()
    return evidence, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('.ldzc_right li'):
        link = item.select_one('a[href][title]')
        if not link:
            continue
        name = clean_text(link.get('title') or link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        detail_url = urljoin(final_url or page_rule['url'], link.get('href', ''))
        duty, evidence_text = fetch_detail_duty(detail_url)
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
            'evidence': evidence_text,
            'confidence': 'high',
            'parser': 'page_list_guizhou_finance_profile_detail_v1',
            'selector_summary': 'leader=.ldzc_right li；name=a[title]；duty=detail 现任/挂职任句；detail=a[href][title]；api_enabled=False',
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
