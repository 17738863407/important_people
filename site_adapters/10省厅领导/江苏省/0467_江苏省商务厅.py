from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    'rule_id': '0467',
    'domain': 'doc.jiangsu.gov.cn',
    'page_type': '人物表格页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_jiangsu_commerce_zoom_inner_tables_v1',
    'leader_region_selector': '#zoom > table',
    'name_selector': '#zoom > table p:first-of-type span[style*="黑体"]',
    'duty_selector': '#zoom > table p:first-of-type span[style*="宋体"]',
    'detail_link_selector': '',
    'content_scope': {
        'start_anchor': '机构领导',
        'end_anchor': '',
        'include_selectors': ['#zoom'],
        'exclude_selectors': [],
    },
    'detail_strategy': {
        'required': False,
        'mode': 'none',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '',
        'detail_parser': '',
        'detail_name_selector': '',
        'detail_duty_selector': '',
        'detail_content_selector': '',
        'max_detail_links': 50,
    },
    'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '#zoom > table',
            'name_selector': '#zoom > table p:first-of-type span[style*="黑体"]',
            'duty_selector': '#zoom > table p:first-of-type span[style*="宋体"]',
            'detail_link_selector': '',
            'content_scope': {
                'start_anchor': '机构领导',
                'end_anchor': '',
                'include_selectors': ['#zoom'],
                'exclude_selectors': [],
            },
        },
        'api': {'enabled': False, 'reason': '在线正文表格直接包含姓名和职务'},
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def extract_name_duty(table) -> tuple[str, str]:
    first_p = table.select_one('p')
    if not first_p:
        return '', ''
    spans = first_p.select('span')
    name_parts = []
    duty_parts = []
    for span in spans:
        style = span.get('style', '')
        text = clean_text(span.get_text(' ', strip=True))
        if not text:
            continue
        if '黑体' in style or 'SimHei' in style:
            name_parts.append(text)
        elif '宋体' in style or 'SimSun' in style:
            duty_parts.append(text)
    name = clean_name(''.join(name_parts))
    duty = clean_text(''.join(duty_parts)).strip('。')
    if not duty:
        first_text = clean_text(first_p.get_text(' ', strip=True))
        match = re.match(r'^(?P<name>[\u4e00-\u9fa5]\s*[\u4e00-\u9fa5]{1,3})\s+(?P<duty>.+)$', first_text)
        if match:
            name = clean_name(match.group('name'))
            duty = clean_text(match.group('duty')).strip('。')
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for table in soup.select('#zoom > table'):
        name, duty = extract_name_duty(table)
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'organization': page_rule['organization'],
            'url': page_rule['url'],
            'name': name,
            'duty': duty,
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_jiangsu_commerce_zoom_inner_tables_v1',
            'selector_summary': 'leader=#zoom > table；name=p:first span黑体；duty=p:first span宋体；detail=none；api_enabled=False',
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
