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
    'rule_id': '0411',
    'domain': 'dhzt.gxrd.gov.cn',
    'page_type': '人物列表完整页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_guangxi_rd_standing_committee_roles_v1',
    'leader_region_selector': '.o_con .pub_2',
    'name_selector': '.pub_2 li p, .pub_2 li img[alt]',
    'duty_selector': '.pub_2 h2',
    'detail_link_selector': '',
    'content_scope': {
        'start_anchor': '',
        'end_anchor': '',
        'include_selectors': ['.o_con'],
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
        'candidate_links': [],
    },
    'risk_flag': '新闻人物或正文干扰；按h2分组精确排除末尾委员名单，保留主任、副主任、秘书长领导分组',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css',
    'locator': {
        'css': {
            'leader_region_selector': '.o_con .pub_2',
            'name_selector': '.pub_2 li p, .pub_2 li img[alt]',
            'duty_selector': '.pub_2 h2',
            'detail_link_selector': '',
            'content_scope': {
                'start_anchor': '',
                'end_anchor': '',
                'include_selectors': ['.o_con'],
                'exclude_selectors': [],
            },
        },
        'api': {'enabled': False, 'reason': '在线页面直接包含常委会主任、副主任、秘书长、委员名单'},
        'migration': {
            'source': 'sequential_static_html_builder',
            'verified_status': 'verified_online',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = text.replace('　', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r'[（(].*?[）)]', '', text)
    return re.sub(r'\s+', '', text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    allowed_roles = {'主任', '副主任', '秘书长'}
    for section in soup.select('.o_con .pub_2'):
        role_node = section.select_one('h2')
        role_text = clean_text(role_node.get_text(' ', strip=True)) if role_node else ''
        role = '委员' if role_text.startswith('委员') else role_text
        if role not in allowed_roles:
            continue
        for item in section.select('li'):
            name_node = item.select_one('p') or item.select_one('img[alt]')
            raw_name = name_node.get_text(' ', strip=True) if name_node and name_node.name != 'img' else ''
            if not raw_name and name_node:
                raw_name = name_node.get('alt', '')
            name = clean_name(raw_name)
            if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name):
                continue
            key = (name, role)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                'name': name,
                'duty': role,
                'detail_url': '',
                'evidence': role,
                'confidence': 'high',
                'parser': 'page_inline_guangxi_rd_standing_committee_roles_v1',
                'selector_summary': 'leader=.o_con .pub_2；name=li p/img[alt]；duty=h2；detail=；api_enabled=False',
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
