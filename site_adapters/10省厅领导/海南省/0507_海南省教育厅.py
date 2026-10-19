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
    'rule_id': '0507',
    'domain': 'edu.hainan.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_hainan_edu_leader_card_v1',
    'leader_region_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
    'name_selector': 'em',
    'duty_selector': 'span',
    'detail_link_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
    'content_scope': {
        'start_anchor': '省委教育工委，省教育厅领导',
        'end_anchor': '领导活动',
        'include_selectors': ['.gkpd-l-nr .gkpd-ld', '.gkpd-l-nr .gkpd-ldd'],
        'exclude_selectors': ['.gkpd-l-nr-x', '.gkpd-r', '.foot'],
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
        'candidate_links': [],
    },
    'risk_flag': '旧选择器为长nth路径，已替换为领导卡片块内em/span字段',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
            'name_selector': 'em',
            'duty_selector': 'span',
            'detail_link_selector': '.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]',
            'content_scope': {
                'start_anchor': '省委教育工委，省教育厅领导',
                'end_anchor': '领导活动',
                'include_selectors': ['.gkpd-l-nr .gkpd-ld', '.gkpd-l-nr .gkpd-ldd'],
                'exclude_selectors': ['.gkpd-l-nr-x', '.gkpd-r', '.foot'],
            },
        },
        'api': {'enabled': False, 'reason': '领导姓名和职务由在线静态 HTML 卡片字段直出'},
        'migration': {
            'source': 'manual_sequential_fix',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.strip('[]【】 ')
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    base_node = soup.select_one('base[href]')
    base_url = base_node.get('href') if base_node else (str(page_rule.get('url', '')) or final_url)
    rows = []
    seen = set()
    for card in soup.select('.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]'):
        name_node = card.select_one('em')
        duty_node = card.select_one('span')
        if not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(' ', strip=True))
        duty = clean_text(duty_node.get_text(' ', strip=True))
        if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
            continue
        detail_url = urljoin(base_url, card.get('href', ''))
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
            'parser': 'page_inline_hainan_edu_leader_card_v1',
            'selector_summary': 'leader=.gkpd-l-nr .gkpd-ld a[href], .gkpd-l-nr .gkpd-ldd a[href]；name=em；duty=span；detail=a[href]；api_enabled=False',
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
