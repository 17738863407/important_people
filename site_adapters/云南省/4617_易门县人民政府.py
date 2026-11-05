from __future__ import annotations

from pathlib import Path
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": '4617'}


def parse_page(html, final_url, page_rule):
    from crawler_core.parsers_v1 import ROLE_WORD_PATTERN

    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    # 使用集中职务边界，最长词优先，保留当前标题中的全部机构前缀。
    roles = sorted(set(ROLE_WORD_PATTERN.pattern.strip('()').split('|')), key=len, reverse=True)
    role_pattern = re.compile('|'.join(re.escape(role) for role in roles))
    for link in soup.select('.conRight > li > span > a[href]'):
        if not link.get('href') or not link.get_text(strip=True):
            continue
        if any(node.has_attr('hidden') or node.get('aria-hidden') == 'true' or 'display:none' in re.sub(r'\s+', '', node.get('style', '')).lower() for node in [link, *link.parents]):
            continue
        text = re.sub(r'\s+', '', link.get_text())
        boundaries = list(role_pattern.finditer(text))
        if not boundaries:
            raise RuntimeError('标题无集中职务边界')
        boundary = boundaries[-1].end()
        duty, name = text[:boundary], text[boundary:]
        if not duty or not re.fullmatch(r'[\u3400-\u9fff·]{2,12}', name):
            raise RuntimeError('领导列表标题职务姓名结构变化')
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
