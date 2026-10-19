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
    'rule_id': '0516',
    'domain': 'ee.xizang.gov.cn',
    'page_type': '人物表格页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'raw_http',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_table_xizang_ee_heading_name_duty_v1',
    'leader_region_selector': '.TRS_UEDITOR table',
    'name_selector': '每个表格第一行职务关键词前姓名',
    'duty_selector': '每个表格第一行职务关键词起始文本',
    'detail_link_selector': '',
    'content_scope': {
        'start_anchor': '领导简介',
        'end_anchor': '',
        'include_selectors': ['.TRS_UEDITOR table'],
        'exclude_selectors': ['.footer', '.header', '.xq-box-left'],
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
    'risk_flag': '旧选择器固定第二表；已改为遍历正文全部领导表格且只读第一行，避免分工混入职务',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    
    'locator_strategy': 'css+table_heading',
    'locator': {
        'css': {
            'leader_region_selector': '.TRS_UEDITOR table',
            'name_selector': '每个表格第一行职务关键词前姓名',
            'duty_selector': '每个表格第一行职务关键词起始文本',
            'detail_link_selector': '',
            'content_scope': {
                'start_anchor': '领导简介',
                'end_anchor': '',
                'include_selectors': ['.TRS_UEDITOR table'],
                'exclude_selectors': ['.footer', '.header', '.xq-box-left'],
            },
        },
        'api': {'enabled': False, 'reason': '在线静态 HTML 表格第一行已包含姓名和职务'},
        'migration': {
            'source': 'manual_sequential_fix',
            'verified_status': 'verified_online',
            'behavior_changed': True,
        },
    },
}


def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'[\u2002\u2003\u2009\u200b]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def clean_name(value: str) -> str:
    return re.sub(r'\s+', '', clean_text(value))


def parse_heading(text: str) -> tuple[str, str]:
    heading = clean_text(text)
    positions = [heading.find(keyword) for keyword in ['党组', '厅长', '副厅长', '巡视员'] if heading.find(keyword) >= 0]
    if not positions:
        return '', ''
    split_at = min(positions)
    name = clean_name(heading[:split_at])
    duty = clean_text(heading[split_at:]).strip('。')
    if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', name) or not duty:
        return '', ''
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for table in soup.select('.TRS_UEDITOR table'):
        first_row = table.select_one('tr.firstRow') or table.select_one('tr')
        if not first_row:
            continue
        heading = clean_text(first_row.get_text(' ', strip=True))
        name, duty = parse_heading(heading)
        if not name or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_table_xizang_ee_heading_name_duty_v1',
            'selector_summary': 'leader=.TRS_UEDITOR table；name=第一行职务关键词前文本；duty=第一行职务关键词后文本；detail=none；api_enabled=False',
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
