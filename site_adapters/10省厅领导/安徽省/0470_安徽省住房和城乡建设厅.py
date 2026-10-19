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

PAGE_RULE = {
    'rule_id': '0470',
    'domain': 'dohurd.ah.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '接口数据加载',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_direct',
    'collector': 'raw_http+api',
    'parser': 'page_api_anhui_housing_public_title_duty_name_v1',
    'leader_region_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[href]',
    'name_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[title]',
    'duty_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[title]',
    'detail_link_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[href]',
    'content_scope': {
        'start_anchor': '机构领导',
        'end_anchor': '',
        'include_selectors': ['.zcwjbox'],
        'exclude_selectors': [],
    },
    'detail_strategy': {
        'required': False,
        'mode': 'none',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '.xxgk-table-list td.title-td a.title[href]',
        'detail_parser': '',
        'detail_name_selector': '',
        'detail_duty_selector': '',
        'detail_content_selector': '',
        'max_detail_links': 50,
    },
    'risk_flag': '入口页仅含列表模板，人物数据由/site/label/8888接口加载',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'api+css',
    'locator': {
        'css': {
            'leader_region_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[href]',
            'name_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[title]',
            'duty_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[title]',
            'detail_link_selector': '.zcwjbox tr.xxgk_nav_con td.info a.title[href]',
            'content_scope': {
                'start_anchor': '机构领导',
                'end_anchor': '',
                'include_selectors': ['.zcwjbox'],
                'exclude_selectors': [],
            },
        },
        'api': {
            'enabled': True,
            'url': 'https://dohurd.ah.gov.cn/site/label/8888',
            'method': 'GET',
            'params': {
                'labelName': 'publicInfoList',
                'siteId': '6804621',
                'organId': '6991',
                'pageSize': '15',
                'catId': '6715221',
                'type': '4',
                'dateFormat': 'yyyy年MM月dd日',
                'file': '/xxgk/publicInfoList_newest2020_zc',
            },
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def split_duty_name(title: str) -> tuple[str, str]:
    text = clean_text(title)
    duty_terms = ['厅长', '副厅长', '组长', '巡视员']
    for name_len in range(2, 5):
        if len(text) <= name_len:
            continue
        name = text[-name_len:]
        duty = clean_text(text[:-name_len]).strip('，,、；;。')
        if re.fullmatch(r'[\u4e00-\u9fa5·]{2,4}', name) and any(duty.endswith(term) for term in duty_terms):
            return duty, name
    return '', ''


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    source_url = str(page_rule.get('url', '')) or final_url
    api_rule = page_rule['locator']['api']
    response = requests.get(
        api_rule['url'],
        params=api_rule['params'],
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': source_url,
            'X-Requested-With': 'XMLHttpRequest',
        },
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'lxml')
    rows = []
    seen = set()
    for link in soup.select('.zcwjbox tr.xxgk_nav_con td.info a.title[href]'):
        title = link.get('title') or link.get_text(' ', strip=True)
        duty, name = split_duty_name(title)
        if not name or not duty:
            continue
        href = str(link.get('href', '')).strip()
        detail_url = ''
        if href and not href.lower().startswith(('#', 'javascript:')):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip('/') != source_url.rstrip('/'):
                detail_url = candidate_url
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
            'parser': 'page_api_anhui_housing_public_title_duty_name_v1',
            'selector_summary': 'api=/site/label/8888；leader=.zcwjbox tr.xxgk_nav_con td.info a.title[href]；title=机构+职务+姓名',
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
