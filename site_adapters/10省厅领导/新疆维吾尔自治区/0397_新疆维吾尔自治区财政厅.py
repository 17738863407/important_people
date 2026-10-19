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

PAGE_RULE = {'rule_id': '0397',
 'domain': 'czt.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_list_xinjiang_finance_detail_caption_v1',
 'leader_region_selector': 'ul.infolist.ldlist.clearfix li',
 'name_selector': 'a.box .txt.elli-s',
 'duty_selector': '详情页 #zoomcon 职务姓名行 / h2.article-subtitle',
 'detail_link_selector': 'a.box[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['ul.infolist.ldlist.clearfix'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a.box[href]',
                     'detail_parser': 'detail_xinjiang_finance_caption_before_name_v1',
                     'detail_name_selector': 'h1.article-title',
                     'detail_duty_selector': '#zoomcon p 包含“职务 + 姓名”的标题行；兜底 h2.article-subtitle',
                     'detail_content_selector': '#zoomcon',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+detail',
 'locator': {'css': {'leader_region_selector': 'ul.infolist.ldlist.clearfix li',
                     'name_selector': 'a.box .txt.elli-s',
                     'duty_selector': '详情页 #zoomcon 职务姓名行 / h2.article-subtitle',
                     'detail_link_selector': 'a.box[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['ul.infolist.ldlist.clearfix'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线领导姓名列表，职务在静态详情页中'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\u2002', ' ').replace('\u2003', ' ')
    text = text.replace('\xa0', ' ').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:。])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def normalize_duty(value: str, name: str) -> str:
    duty = clean_text(value)
    duty = duty.replace(name, '')
    duty = re.sub(r'^[：:，,、；;\s]+|[：:，,、；;\s]+$', '', duty)
    return clean_text(duty).strip('。')


def extract_caption_duty(soup: BeautifulSoup, name: str) -> str:
    content = soup.select_one('#zoomcon') or soup.select_one('.article-content')
    if content:
        for node in content.find_all(['p', 'div'], recursive=True):
            text = clean_text(node.get_text(' ', strip=True))
            if not text or name not in text:
                continue
            if re.search(rf'^{re.escape(name)}[，,、]\s*[男女]', text):
                continue
            before_name = text.split(name, 1)[0]
            duty = normalize_duty(before_name, name)
            if duty and any(word in duty for word in ['党组', '厅长', '巡视员', '总经济师', '总会计师']):
                return duty
    subtitle = soup.select_one('h2.article-subtitle')
    return normalize_duty(subtitle.get_text(' ', strip=True), name) if subtitle else ''


def fetch_detail_duty(url: str, list_name: str) -> tuple[str, str]:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return '', list_name
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, 'lxml')
    title = soup.select_one('h1.article-title')
    detail_name = clean_name(title.get_text(' ', strip=True)) if title else list_name
    if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,10}', detail_name):
        detail_name = list_name
    duty = extract_caption_duty(soup, detail_name)
    return duty, detail_name


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('ul.infolist.ldlist.clearfix li'):
        link = item.select_one('a.box[href]')
        name_node = item.select_one('a.box .txt.elli-s')
        if not link or not name_node:
            continue
        list_name = clean_name(name_node.get_text(' ', strip=True) or link.get('title', ''))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,10}', list_name):
            continue
        detail_url = urljoin(final_url, link.get('href', ''))
        duty, detail_name = fetch_detail_duty(detail_url, list_name)
        name = detail_name or list_name
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
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_list_xinjiang_finance_detail_caption_v1',
            'selector_summary': 'leader=ul.infolist.ldlist.clearfix li；name=a.box .txt.elli-s；duty=detail #zoomcon caption/h2.article-subtitle；detail=a.box[href]；api_enabled=False',
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
