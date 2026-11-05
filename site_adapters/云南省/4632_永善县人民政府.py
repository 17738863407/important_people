"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '#RightContentGov .lingdao内.list .sortName绑定紧邻ul，li.title姓名与图片a链接，仅领导列表、隐藏过滤、DOM序。', 'rule_id': '4632'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for heading in soup.select('#RightContentGov .lingdao .list'):
        duty = text(heading.select_one('.sortName'))
        listing = heading.find_next_sibling('ul')
        if listing is None:
            raise ValueError('职务分组缺少名单')
        for card in listing.select('li'):
            if not visible(card):
                continue
            name = re.sub(r'\s+', '', text(card.select_one('.title')))
            link = card.select_one('a[href]')
            if not link or not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
                raise ValueError('领导字段异常')
            rows.append({'name': name, 'evidence': duty, 'detail_url': urljoin(final_url, link['href'])})
    return rows

def resolve_project_dir():
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir():
            return parent
    raise RuntimeError('未找到项目根目录')

def main():
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f'输出文件：{output_path}')

if __name__ == '__main__':
    main()
