from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    'rule_id': '0469',
    'domain': 'dofcom.nx.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_to_detail',
    'collector': 'static_http',
    'parser': 'page_list_ningxia_commerce_online_detail_v1',
    'leader_region_selector': '#part21 ul.swtld li',
    'name_selector': '#part21 ul.swtld li p a',
    'duty_selector': '详情页 .view 首段分号后职务',
    'detail_link_selector': '#part21 ul.swtld li p a[href]',
    'content_scope': {
        'start_anchor': '商务厅领导',
        'end_anchor': '主要职责',
        'include_selectors': ['#part21 ul.swtld'],
        'exclude_selectors': ['.bljld'],
    },
    'detail_strategy': {
        'required': True,
        'mode': 'list_to_detail',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '#part21 ul.swtld li p a[href]',
        'detail_parser': 'detail_ningxia_commerce_view_semicolon_duty_v1',
        'detail_name_selector': '列表姓名',
        'detail_duty_selector': '.view 首段分号后职务',
        'detail_content_selector': '.view',
        'max_detail_links': 50,
    },
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'css+detail',
    'locator': {
        'css': {
            'leader_region_selector': '#part21 ul.swtld li',
            'name_selector': '#part21 ul.swtld li p a',
            'duty_selector': '详情页 .view 首段分号后职务',
            'detail_link_selector': '#part21 ul.swtld li p a[href]',
            'content_scope': {
                'start_anchor': '商务厅领导',
                'end_anchor': '主要职责',
                'include_selectors': ['#part21 ul.swtld'],
                'exclude_selectors': ['.bljld'],
            },
        },
        'api': {'enabled': False, 'reason': '列表页和详情页均为在线静态 HTML'},
    },
}


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def fetch_html(url: str) -> str:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25, verify=False)
        response.raise_for_status()
    except requests.RequestException:
        return ''
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, 'lxml')
    links = []
    for item in soup.select('#part21 ul.swtld li'):
        link = item.select_one('p a[href]')
        if not link:
            continue
        name = clean_name(link.get_text(' ', strip=True))
        href = link.get('href', '')
        detail_url = urljoin(base_url, href) if href and not href.startswith('javascript') else ''
        detail = urlparse(detail_url)
        source = urlparse(base_url)
        if (
            detail.scheme not in {'http', 'https'}
            or detail.netloc.lower() != source.netloc.lower()
            or detail.fragment
            or detail.path.rstrip('/') == source.path.rstrip('/')
            or not detail.path.lower().endswith(('.html', '.htm'))
        ):
            detail_url = ''
        if re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            links.append((name, detail_url))
    return links


def fetch_detail_duty(url: str) -> str:
    html = fetch_html(url)
    if not html:
        return ''
    soup = BeautifulSoup(html, 'lxml')
    view = soup.select_one('.view')
    text = clean_text(view.get_text(' ', strip=True) if view else soup.get_text(' ', strip=True))
    first_part = re.split(r'工作分工[:：]', text, maxsplit=1)[0]
    match = re.search(r'[；;]\s*(?P<duty>[^。]+)', first_part)
    if match:
        return clean_text(match.group('duty')).strip('。')
    return ''


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    base_url = final_url or page_rule['url']
    links = extract_links(html, base_url)
    rows = []
    seen = set()
    for name, detail_url in links:
        if not detail_url:
            continue
        duty = fetch_detail_duty(detail_url)
        if not duty:
            continue
        key = (name, duty, detail_url)
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
            'parser': 'page_list_ningxia_commerce_online_detail_v1',
            'selector_summary': 'leader=#part21 ul.swtld li；name=p a；duty=detail .view 分号后职务；detail=p a[href]；api_enabled=False',
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
