from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4621'}


def parse_page(html, final_url, page_rule):
    """按政府领导区域的职务分组及卡片顺序提取。"""
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for group in soup.select('dl.leader'):
        title = group.find('dt', recursive=False)
        if title is None:
            raise RuntimeError('领导分组缺少职务标题')
        for card in group.select('dd li'):
            label = card.select_one('a.info .name')
            link = card.select_one('a.info[href]')
            if label is None or link is None:
                raise RuntimeError('人物卡片字段缺失')
            if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [label, *label.parents]):
                continue
            raw_name = re.sub(r'\s+', '', label.get_text())
            match = re.fullmatch(r'([\u4e00-\u9fff·]{2,12})(（[^（）]+）)?', raw_name)
            if not match:
                raise RuntimeError('人物姓名字段异常')
            name, qualifier = match.groups()
            duty = title.get_text('', strip=True)
            if duty.endswith(name):
                duty = duty[:-len(name)].strip()
            rows.append({'name': name, 'evidence': duty + (qualifier or ''), 'detail_url': urljoin(final_url, link['href'])})
    if not rows:
        raise RuntimeError('政府领导分组为空')
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
