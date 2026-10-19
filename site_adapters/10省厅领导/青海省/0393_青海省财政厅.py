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

PAGE_RULE = {'rule_id': '0393',
 'domain': 'czt.qinghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_qinghai_finance_query_links_v1',
 'leader_region_selector': 'a[href^="query/"]',
 'name_selector': '链接文本职务起始词前',
 'duty_selector': '链接文本职务起始词后',
 'detail_link_selector': 'a[href^="query/"]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.zwgkbg'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href^="query/"]',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '.zwgkbg',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+text_parse',
 'locator': {'css': {'leader_region_selector': 'a[href^="query/"]',
                     'name_selector': '链接文本职务起始词前',
                     'duty_selector': '链接文本职务起始词后',
                     'detail_link_selector': 'a[href^="query/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.zwgkbg'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面 query 领导链接已直出姓名和职务'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online_inline',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def split_name_duty(value: str) -> tuple[str, str] | None:
    text = clean_text(value)
    markers = ['党组', '青海省纪委', '副厅长', '厅长', '巡视员', '援青办公室']
    positions = [text.find(marker) for marker in markers if text.find(marker) > 0]
    if not positions:
        return None
    pos = min(positions)
    name = re.sub(r'\s+', '', text[:pos])
    duty = clean_text(text[pos:])
    if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for link in soup.select('a[href^="query/"]'):
        parsed = split_name_duty(link.get_text(' ', strip=True))
        if not parsed:
            continue
        name, duty = parsed
        detail_url = urljoin(final_url or page_rule['url'], link.get('href', ''))
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
            'parser': 'page_inline_qinghai_finance_query_links_v1',
            'selector_summary': 'leader=a[href^="query/"]；name=链接文本职务起始词前；duty=链接文本职务起始词后；detail=a[href^="query/"]；api_enabled=False',
        })
    if rows:
        return rows

    api_url = urljoin(page_rule['url'], 'index/get/leaderlist')
    response = requests.post(
        api_url,
        headers={'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'},
        timeout=20,
    )
    response.raise_for_status()
    for item in response.json().get('list', []):
        name = re.sub(r'\s+', '', str(item.get('Title') or ''))
        duty = clean_text(str(item.get('NextTitle') or ''))
        detail_id = str(item.get('ID') or '').strip()
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty or not re.fullmatch(r'\d+', detail_id):
            continue
        rows.append({
            'organization': page_rule['organization'],
            'url': page_rule['url'],
            'name': name,
            'duty': duty,
            'detail_url': urljoin(page_rule['url'], f'query/{detail_id}.html'),
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_qinghai_finance_query_links_v1',
            'selector_summary': 'POST index/get/leaderlist；Title姓名；NextTitle职务；ID详情页',
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
