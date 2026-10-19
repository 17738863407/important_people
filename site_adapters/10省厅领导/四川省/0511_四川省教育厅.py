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
    'rule_id': '0511',
    'domain': 'edu.sc.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_to_detail',
    'collector': 'static_http',
    'parser': 'page_list_sichuan_edu_detail_current_sentence_v1',
    'leader_region_selector': '.gknr_list.jgszxxgk dd a[href]',
    'name_selector': '.gknr_list.jgszxxgk dd a',
    'duty_selector': '详情页简历段落“现任...”句',
    'detail_link_selector': '.gknr_list.jgszxxgk dd a[href]',
    'content_scope': {
        'start_anchor': '省委教育工委、教育厅领导',
        'end_anchor': '机构职能',
        'include_selectors': ['.gknr_list.jgszxxgk'],
        'exclude_selectors': ['.footer', '.header', '.gknr_list:not(.jgszxxgk)'],
    },
    'detail_strategy': {
        'required': True,
        'mode': 'list_to_detail',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '.gknr_list.jgszxxgk dd a[href]',
        'detail_parser': 'detail_sichuan_edu_current_sentence_v1',
        'detail_name_selector': '详情页标题/名单链接',
        'detail_duty_selector': '简历段落现任句',
        'detail_content_selector': '正文简历段落',
        'max_detail_links': 30,
        'candidate_links': [],
    },
    'risk_flag': '列表页只有姓名；需逐个详情页从简历现任句提取职务',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css+detail_text',
    'locator': {
        'css': {
            'leader_region_selector': '.gknr_list.jgszxxgk dd a[href]',
            'name_selector': '.gknr_list.jgszxxgk dd a',
            'duty_selector': '详情页简历段落“现任...”句',
            'detail_link_selector': '.gknr_list.jgszxxgk dd a[href]',
            'content_scope': {
                'start_anchor': '省委教育工委、教育厅领导',
                'end_anchor': '机构职能',
                'include_selectors': ['.gknr_list.jgszxxgk'],
                'exclude_selectors': ['.footer', '.header', '.gknr_list:not(.jgszxxgk)'],
            },
        },
        'api': {'enabled': False, 'reason': '列表与详情页均为静态 HTML'},
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def fetch_detail(url: str, fallback_name: str) -> tuple[str, str, str]:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return fallback_name, '', ''
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, 'lxml')
    text = '\n'.join(clean_text(part) for part in soup.get_text('\n', strip=True).split('\n') if part.strip())
    name = fallback_name
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    title_match = re.match(r'([\u4e00-\u9fa5·]{2,8})-', clean_text(title))
    if title_match:
        name = title_match.group(1)
    duty = ''
    evidence = ''
    pattern = re.compile(rf'({re.escape(name)}，.*?现任(?P<duty>[^。]+)。)')
    match = pattern.search(text)
    if not match:
        match = re.search(r'([\u4e00-\u9fa5·]{2,8}，.*?现任(?P<duty>[^。]+)。)', text)
    if match:
        duty = clean_text(match.group('duty')).strip('。')
        evidence = clean_text(match.group(1))
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    base_url = final_url
    rows = []
    seen = set()
    for link in soup.select('.gknr_list.jgszxxgk dd a[href]'):
        nav_name = clean_name(link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', nav_name):
            continue
        detail_url = urljoin(base_url, link.get('href', ''))
        name, duty, evidence = fetch_detail(detail_url, nav_name)
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        key = (name, duty, detail_url)
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
            'parser': 'page_list_sichuan_edu_detail_current_sentence_v1',
            'selector_summary': 'leader=.gknr_list.jgszxxgk dd a[href]；name=list a/detail title；duty=detail 简历现任句；detail=list a[href]；api_enabled=False',
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
