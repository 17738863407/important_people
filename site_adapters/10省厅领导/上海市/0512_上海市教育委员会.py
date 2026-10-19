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
    'rule_id': '0512',
    'page_type': '人物列表完整页',
    'structure_group': 'shanghai_edu_leader_title_list',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_inline_shanghai_edu_leader_titles_v2',
    'leader_region_selector': '.opened_right_news #listContent li a[href]',
    'name_selector': '标题末尾姓名',
    'duty_selector': '标题去掉末尾姓名',
    'detail_link_selector': '.opened_right_news #listContent li a[href]',
    'content_scope': {
        'start_anchor': '机构领导',
        'end_anchor': '',
        'include_selectors': ['.opened_right_news #listContent'],
        'exclude_selectors': ['.breadcrumb_trail', '.content_wrap', '.footer', '.header'],
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
    'risk_flag': '页面页脚含验证码故障提示，会触发在线采集的误判；已核验原始HTTP正文完整，限定机构领导列表并按标题末尾解析',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'custom_parse_page',
    'locator': {
        'css': {
            'leader_region_selector': '.opened_right_news #listContent li a[href]',
            'name_selector': '标题末尾姓名',
            'duty_selector': '标题去掉末尾姓名',
            'detail_link_selector': '.opened_right_news #listContent li a[href]',
            'content_scope': {
                'start_anchor': '机构领导',
                'end_anchor': '',
                'include_selectors': ['.opened_right_news #listContent'],
                'exclude_selectors': ['.breadcrumb_trail', '.content_wrap', '.footer', '.header'],
            },
        },
        'api': {'enabled': False, 'reason': '在线原始HTML列表标题已包含姓名和职务'},
        'migration': {
            'source': 'manual_sequential_fix',
            'verified_status': 'verified_online',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def parse_title(title: str) -> tuple[str, str]:
    text = clean_text(title)
    match = re.match(r'^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fa5·]{2,4})$', text)
    if not match:
        return '', ''
    name = match.group('name')
    duty = clean_text(match.group('duty')).strip('。')
    if any(word in duty for word in ['领导及工作分工', '机构领导']) or not re.search(r'主任|书记|巡视员|委员', duty):
        return '', ''
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    base_url = final_url
    rows = []
    seen = set()
    for link in soup.select('.opened_right_news #listContent li a[href]'):
        title = clean_text(link.get_text(' ', strip=True))
        name, duty = parse_title(title)
        if not name or not duty:
            continue
        detail_url = urljoin(base_url, link.get('href', ''))
        key = detail_url
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_shanghai_edu_leader_titles_v2',
        })
    if not rows:
        raise RuntimeError('机构领导列表未解析到有效人物标题')
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
