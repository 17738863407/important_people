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

PAGE_RULE = {'rule_id': '0254',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_cmde_child_list_paragraph_v1',
 'leader_region_selector': 'div.child-list.columnPage p',
 'name_selector': '段落首个姓名',
 'duty_selector': '姓名后文本',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'risk_flag': '普通请求返回202动态防护空壳，必须取得浏览器渲染后的领导信息区域；页面无独立人物详情页',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div.child-list.columnPage p',
                     'name_selector': '段落首个姓名',
                     'duty_selector': '姓名后文本',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_snapshot',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').replace('\xa0', ' ')).strip()


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', (value or '').replace('\xa0', ' ')).strip()


def is_name_text(value: str) -> bool:
    return bool(re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', clean_name(value)))


def split_name_duty(text: str) -> tuple[str, str]:
    text = clean_text(text)
    match = re.fullmatch(r'((?:[\u4e00-\u9fa5·]\s*){2,8})\s+(.+)', text)
    if not match:
        return '', ''
    return clean_name(match.group(1)), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    for paragraph in soup.select('div.child-list.columnPage p'):
        text = clean_text(paragraph.get_text(' ', strip=True))
        name, duty = split_name_duty(text)
        if not is_name_text(name) or not duty:
            continue
        rows.append({
            'organization': page_rule['organization'],
            'url': page_rule['url'],
            'name': name,
            'duty': duty,
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_cmde_child_list_paragraph_v1',
            'selector_summary': 'leader=div.child-list.columnPage p；name=段落首个姓名；duty=姓名后文本；detail=current_page；api_enabled=False',
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
