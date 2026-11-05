from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4620'}


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.conRight > li > span > a[href]'):
        if not link.get('href') or not link.get_text(strip=True):
            continue
        if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [link, *link.parents]):
            continue
        match = re.fullmatch(r'(.+?)\s+([\u3400-\u9fff·]{2,12})', link.get_text('', strip=True))
        if not match:
            raise RuntimeError('领导列表标题职务姓名结构变化')
        duty, name = match.groups()
        rows.append({'name': name, 'evidence': duty, 'detail_url': urljoin(final_url, link['href'])})
    if not rows:
        raise RuntimeError('领导列表为空')
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
