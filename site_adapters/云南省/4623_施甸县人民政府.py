from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4623'}


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for group in soup.select('.szfld_list'):
        title = group.find('p', class_='szfld_name', recursive=False)
        if title is None:
            raise RuntimeError('领导分组标题缺失')
        for link in group.select('ul.ld_lsit > li > a[href]'):
            if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [link, *link.parents]):
                continue
            name_node = link.find('p', recursive=False)
            duty = title.get_text('', strip=True)
            raw = name_node.get_text('', strip=True) if name_node else ''
            if not raw.startswith(duty):
                raise RuntimeError('卡片职务前缀与组标题不一致')
            name = re.sub(r'\s+', '', raw[len(duty):])
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,12}', name):
                raise RuntimeError('姓名字段异常')
            rows.append({'name': name, 'evidence': duty, 'detail_url': urljoin(final_url, link['href']), 'raw_evidence': raw})
    if not rows:
        raise RuntimeError('领导卡片为空')
    return rows


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
