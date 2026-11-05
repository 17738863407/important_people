"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.ldwrap .dzcy li a9个领导卡片，首p姓名、p.jj职务，含网页明确的高新区兼任，排除目录导航，DOM序及隐藏过滤。', 'rule_id': '4660'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for card in soup.select('.ldwrap .dzcy li a[href]'):
        if not visible(card):
            continue
        name = re.sub(r'\s+', '', text(card.find('p')))
        duty = text(card.select_one('p.jj'))
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise ValueError('人物字段异常')
        rows.append({'name': name, 'evidence': duty, 'detail_url': urljoin(final_url, card['href'])})
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
