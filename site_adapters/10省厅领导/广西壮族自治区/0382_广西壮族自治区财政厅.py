from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0382',
 'domain': 'czt.gxzf.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guangxi_finance_title_list_v1',
 'leader_region_selector': '.zfxxgk-more-list li',
 'name_selector': 'a[title] title中职务起始词前',
 'duty_selector': 'a[title] title中职务起始词后',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.zfxxgk-more-list'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '.zfxxgk-more-list',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css+title_parse',
 'locator': {'css': {'leader_region_selector': '.zfxxgk-more-list li',
                     'name_selector': 'a[title] title中职务起始词前',
                     'duty_selector': 'a[title] title中职务起始词后',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.zfxxgk-more-list'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线列表 title 直出完整姓名和职务'},
             'migration': {'source': 'sequential_static_html_builder', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def split_name_duty(title: str) -> tuple[str, str] | None:
    text = clean_text(title)
    markers = ['自治区纪委', '党组', '厅长', '副厅长', '巡视员']
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
    for item in soup.select('.zfxxgk-more-list li'):
        link = item.select_one('a[href]')
        if not link:
            continue
        parsed = split_name_duty(link.get('title') or link.get_text(' ', strip=True))
        if not parsed:
            continue
        name, duty = parsed
        detail_url = urljoin(final_url or page_rule['url'], link.get('href', ''))
        if detail_url.rstrip('/') == str(page_rule['url']).rstrip('/'):
            detail_url = ''
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_guangxi_finance_title_list_v1',
            'selector_summary': 'leader=.zfxxgk-more-list li；name=a[title]职务起始词前；duty=a[title]职务起始词后；detail=a[href]；api_enabled=False',
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
