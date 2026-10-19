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

PAGE_RULE = {
    'rule_id': '0463',
    'domain': 'dnr.gxzf.gov.cn',
    'page_type': '多人物详情合并页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_gx_dnr_leader_window_cards_v1',
    'leader_region_selector': '#LDcontent .bt-box1',
    'name_selector': '#LDcontent .bt-box1 h5 span',
    'duty_selector': '#LDcontent .bt-box1 h5',
    'detail_link_selector': '#LDcontent .bt-box1 p a[href]',
    'content_scope': {
        'start_anchor': '领导之窗',
        'end_anchor': '',
        'include_selectors': ['#LDcontent'],
        'exclude_selectors': ['#LDtab'],
    },
    'detail_strategy': {
        'required': False,
        'mode': 'none',
        'detail_collector_type': 'static_http',
        'detail_link_selector': '#LDcontent .bt-box1 p a[href]',
        'detail_parser': '',
        'detail_name_selector': '',
        'detail_duty_selector': '',
        'detail_content_selector': '',
        'max_detail_links': 50,
        'candidate_links': [],
    },
    'risk_flag': '新闻人物或正文干扰',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '#LDcontent .bt-box1',
            'name_selector': '#LDcontent .bt-box1 h5 span',
            'duty_selector': '#LDcontent .bt-box1 h5',
            'detail_link_selector': '#LDcontent .bt-box1 p a[href]',
            'content_scope': {
                'start_anchor': '领导之窗',
                'end_anchor': '',
                'include_selectors': ['#LDcontent'],
                'exclude_selectors': ['#LDtab'],
            },
        },
        'api': {'enabled': False, 'reason': '在线静态页面包含完整领导卡片'},
        'migration': {
            'source': 'sequential_detail_chain_builder',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for card in soup.select('#LDcontent .bt-box1'):
        name_node = card.select_one('h5 span')
        title_node = card.select_one('h5')
        if not name_node or not title_node:
            continue
        name = re.sub(r'\s+', '', clean_text(name_node.get_text(' ', strip=True)))
        title_text = clean_text(title_node.get_text(' ', strip=True))
        duty = clean_text(title_text.replace(name, '', 1)).strip('，,、；;。')
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_link = card.select_one('p a[href]')
        detail_url = urljoin(final_url or page_rule['url'], detail_link.get('href', '')) if detail_link else ''
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
            'parser': 'page_inline_gx_dnr_leader_window_cards_v1',
            'selector_summary': 'leader=#LDcontent .bt-box1；name=h5 span；duty=h5去除姓名；detail=p a[href]；api_enabled=False',
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
