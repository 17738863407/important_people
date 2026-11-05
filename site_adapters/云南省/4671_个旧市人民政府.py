"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.ny-ld-a政府领导容器内.item及.dl li卡片，首位.p2完整现任句，余项.p显式职务，产业园区领导按本卡片职务保留，不沿用副市长组标题；排除.ny-ld-b机构，DOM序及隐藏过滤。', 'cleaning_note': '首位卡片现任句删除现任与句末句号，完整保留兼任及（兼）限定。', 'rule_id': '4671'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.ny-ld-a .box .item > a, .ny-ld-a .dl li > a'):
        if not visible(link):
            continue
        name = re.sub(r'[\s\u200b\u200d\ufeff]+', '', text(link.select_one('.h4')))
        raw = text(link.select_one('.p2'))
        match = re.search(r'现任([^。]+)', raw)
        duty = match.group(1).strip() if match else text(link.select_one('.p'))
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise ValueError('领导姓名或职务字段异常')
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
