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
    'rule_id': '0464',
    'domain': 'dnr.henan.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_to_detail',
    'collector': 'static_http',
    'parser': 'page_list_henan_dnr_leader_detail_boxstyle_v1',
    'leader_region_selector': '.leader-list li a[href]',
    'name_selector': '.leader-list li a',
    'duty_selector': '详情页 .boxStyle .lader-right li:first-of-type p',
    'detail_link_selector': '.leader-list li a[href]',
    'content_scope': {
        'start_anchor': '领导信息',
        'end_anchor': '',
        'include_selectors': ['.leader-list'],
        'exclude_selectors': [],
    },
    'detail_strategy': {
        'required': True,
        'mode': 'list_to_detail',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '.leader-list li a[href]',
        'detail_parser': 'detail_henan_dnr_boxstyle_first_duty_v1',
        'detail_name_selector': '列表姓名',
        'detail_duty_selector': '.boxStyle .lader-right li:first-of-type p',
        'detail_content_selector': '.boxStyle',
        'max_detail_links': 50,
        'candidate_links': [],
    },
    'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css+detail',
    'locator': {
        'css': {
            'leader_region_selector': '.leader-list li a[href]',
            'name_selector': '.leader-list li a',
            'duty_selector': '详情页 .boxStyle .lader-right li:first-of-type p',
            'detail_link_selector': '.leader-list li a[href]',
            'content_scope': {
                'start_anchor': '领导信息',
                'end_anchor': '',
                'include_selectors': ['.leader-list'],
                'exclude_selectors': [],
            },
        },
        'api': {'enabled': False, 'reason': '列表页和详情页均为静态 HTML'},
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def fetch_detail_duty(url: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return ''
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, 'lxml')
    duty_node = soup.select_one('.boxStyle .lader-right li:first-of-type p')
    if duty_node:
        return clean_text(duty_node.get_text(' ', strip=True)).strip('。')
    box = soup.select_one('.boxStyle')
    if not box:
        return ''
    text = clean_text(box.get_text(' ', strip=True))
    match = re.search(r'领导职务[:：]\s*(?P<duty>.*?)\s*领导简历[:：]', text)
    return clean_text(match.group('duty')).strip('。') if match else ''


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for link in soup.select('.leader-list li a[href]'):
        name = clean_name(link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        duty = fetch_detail_duty(detail_url)
        if not duty:
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
            'parser': 'page_list_henan_dnr_leader_detail_boxstyle_v1',
            'selector_summary': 'leader=.leader-list li a[href]；name=a；duty=detail .boxStyle .lader-right li:first p；detail=a[href]；api_enabled=False',
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
