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
    'rule_id': '0510',
    'page_type': '人物表格页',
    'structure_group': '',
    'reuse_scope': 'single_page',
    'load_mode': '静态HTML直出',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'static_http',
    'parser': 'page_table_nanchang_edu_mso_leader_v1',
    'leader_region_selector': '#zoom table.MsoNormalTable',
    'name_selector': '表格文本首个姓名',
    'duty_selector': '表格文本“职务：”后一行',
    'detail_link_selector': '',
    'content_scope': {
        'start_anchor': '领导简介',
        'end_anchor': 'AB岗制',
        'include_selectors': ['#zoom table.MsoNormalTable'],
        'exclude_selectors': ['.header', '.footer', '.nav'],
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
        'max_detail_links': 0,
    },
    'risk_flag': '旧选择器固定第5个表格会漏人；已改为遍历领导简介下全部MsoNormalTable',
    'confidence': 'high',
    'profile_reusable': '',
    'profile_judgement': '',
    'filter_policy': 'strong_no_wordlist',
    'locator_strategy': 'css+table_text',
    'locator': {
        'css': {
            'leader_region_selector': '#zoom table.MsoNormalTable',
            'name_selector': '表格文本首个姓名',
            'duty_selector': '表格文本“职务：”后一行',
            'detail_link_selector': '',
            'content_scope': {
                'start_anchor': '领导简介',
                'end_anchor': 'AB岗制',
                'include_selectors': ['#zoom table.MsoNormalTable'],
                'exclude_selectors': ['.header', '.footer', '.nav'],
            },
        },
        'api': {'enabled': False, 'reason': '本地静态 HTML 表格已包含姓名和职务'},
        'migration': {
            'source': 'manual_sequential_fix',
            'verified_status': 'verified_snapshot_only',
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


def parse_table(table) -> tuple[str, str, str]:
    lines = [clean_text(line) for line in table.get_text('\n', strip=True).split('\n')]
    lines = [line for line in lines if line]
    name = ''
    for line in lines:
        candidate = clean_name(line)
        if re.fullmatch(r'[\u4e00-\u9fa5·]{2,8}', candidate) and candidate not in {'职务', '职责'}:
            name = candidate
            break
    duty = ''
    for index, line in enumerate(lines):
        if line.startswith('职务'):
            inline = re.sub(r'^职务[:：]?', '', line).strip()
            if inline:
                duty = inline
            elif index + 1 < len(lines):
                duty = lines[index + 1]
            break
    return name, clean_text(duty).strip('。'), clean_text(' '.join(lines))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for table in soup.select('#zoom table.MsoNormalTable'):
        text = clean_text(table.get_text(' ', strip=True))
        if '职务' not in text or '职责' not in text:
            continue
        name, duty, _ = parse_table(table)
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
            'parser': 'page_table_nanchang_edu_mso_leader_v1',
            'selector_summary': 'leader=#zoom table.MsoNormalTable；name=表格文本首个姓名；duty=职务后一行；detail=none；api_enabled=False',
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
