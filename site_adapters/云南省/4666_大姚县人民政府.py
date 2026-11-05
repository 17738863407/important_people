"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': 'ul.ldul li a[title]八个领导卡片，标题【职务】姓名边界明确，保留完整县委及公安职务，DOM序、隐藏过滤。', 'cleaning_note': '标题按【】边界拆分职务与姓名，删除职务外围展示括号。', 'rule_id': '4666'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('ul.ldul li a[title][href]'):
        if not visible(link):
            continue
        match = re.fullmatch(r'【([^】]+)】\s*([\u4e00-\u9fff·\s]{2,12})', link['title'].strip())
        if not match:
            raise ValueError('领导卡片标题结构变化')
        name = re.sub(r'\s+', '', match.group(2))
        rows.append({'name': name, 'evidence': match.group(1), 'detail_url': urljoin(final_url, link['href'])})
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
