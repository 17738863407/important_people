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

def clean_text(value: str) -> str:
    text = (value or '').replace('\u3000', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def parse_table(table) -> tuple[str, str, str]:
    lines = [clean_text(line) for line in table.get_text('\n', strip=True).splitlines()]
    lines = [line for line in lines if line]
    if '职位：' not in lines or '简历：' not in lines:
        return '', '', ''
    name = re.sub(r'[（(][^）)]*[）)]$', '', lines[0]).strip()
    if not re.fullmatch(r'[\u4e00-\u9fa5·]{2,6}', name):
        return '', '', ''
    duty_index = lines.index('职位：') + 1
    resume_index = lines.index('简历：')
    duty = clean_text(''.join(lines[duty_index:resume_index])).strip('。')
    return name, duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for table in soup.select('table'):
        name, duty, evidence = parse_table(table)
        if not name or not duty:
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
            'parser': 'page_inline_nanchang_fgw_table_fields_v1',
        })
    return rows


PAGE_RULE = {
    'rule_id': '0554',
    'page_type': '人物表格页',
    'structure_group': 'nanchang_fgw_leader_tables',
    'reuse_scope': 'single_page',
    'load_mode': '动态DOM渲染',
    'fetch_mode': 'online',
    'extract_mode': 'list_direct',
    'collector': 'browser_dom',
    'parser': 'page_inline_nanchang_fgw_table_fields_v1',
    'locator_strategy': 'custom_parse_page',
    'risk_flag': '普通 HTTP 返回 403；每位领导一个表格，职位字段与简历字段边界明确',
    'confidence': 'high',
}


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
