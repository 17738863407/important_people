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
    'rule_id': '0506',
    'domain': 'edu.gd.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_to_detail',
    'collector': 'browser_dom',
    'parser': 'page_list_guangdong_edu_detail_duty_field_v1',
    'leader_region_selector': 'a[href*="/zwgknew/zzjg/ld/content/post_"]',
    'name_selector': '领导详情链接文本',
    'duty_selector': '详情页.newsList.right p:contains("职务")',
    'detail_link_selector': 'a[href*="/zwgknew/zzjg/ld/content/post_"]',
    'content_scope': {
        'start_anchor': '领导之窗',
        'end_anchor': '',
        'include_selectors': ['.aside.left', '.newsList.right'],
        'exclude_selectors': ['.header', '.footer', '.pos'],
    },
    'detail_strategy': {
        'required': True,
        'mode': 'list_to_detail',
        'detail_collector_type': 'static_http',
        'detail_link_selector': 'a[href*="/zwgknew/zzjg/ld/content/post_"]',
        'detail_parser': 'detail_guangdong_edu_duty_field_v1',
        'detail_name_selector': '.aside.left li.active a',
        'detail_duty_selector': '.newsList.right p first 职务',
        'detail_content_selector': '.newsList.right',
        'max_detail_links': 30,
    },
    'risk_flag': '领导之窗为左侧名单加右侧详情结构；需逐个详情页读取职务字段',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'css+detail',
    'locator': {
        'css': {
            'leader_region_selector': 'a[href*="/zwgknew/zzjg/ld/content/post_"]',
            'name_selector': '领导详情链接文本',
            'duty_selector': '详情页.newsList.right p:contains("职务")',
            'detail_link_selector': 'a[href*="/zwgknew/zzjg/ld/content/post_"]',
            'content_scope': {
                'start_anchor': '领导之窗',
                'end_anchor': '',
                'include_selectors': ['.aside.left', '.newsList.right'],
                'exclude_selectors': ['.header', '.footer', '.pos'],
            },
        },
        'api': {'enabled': False, 'reason': '在线领导名单与详情正文均在静态 HTML 中'},
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
    active_link = soup.select_one('.aside.left li.active a')
    name = clean_name(active_link.get_text(' ', strip=True)) if active_link else fallback_name
    duty = ''
    evidence = ''
    for node in soup.select('.newsList.right p, .photo p'):
        text = clean_text(node.get_text(' ', strip=True))
        if text.startswith('职务'):
            duty = re.sub(r'^职务[:：]\s*', '', text).strip('。')
            evidence = text
            break
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    base_node = soup.select_one('base[href]')
    base_url = base_node.get('href') if base_node else final_url
    rows = []
    seen = set()
    for link in soup.select('a[href*="/zwgknew/zzjg/ld/content/post_"]'):
        nav_name = clean_name(link.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', nav_name):
            continue
        detail_url = urljoin(base_url, link.get('href', ''))
        name, duty, evidence = fetch_detail(detail_url, nav_name)
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
            continue
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        if detail_url.rstrip('/') == final_url.rstrip('/'):
            detail_url = ''
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty if duty else '',
            'confidence': 'high',
            'parser': 'page_list_guangdong_edu_detail_duty_field_v1',
            'selector_summary': 'leader=.aside.left li a[href]；name=.aside.left li a/detail active；duty=detail .newsList.right p 职务；detail=.aside.left li a[href]；api_enabled=False',
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
