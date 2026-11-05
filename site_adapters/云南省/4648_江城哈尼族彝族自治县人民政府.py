"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.leaderTab li p a九个人物导航，最后空白分隔姓名、左侧职务排版空白删除，DOM序、隐藏过滤；当前页链接作为详情留空。', 'cleaning_note': '导航原文职务与姓名按末个空白拆分，县  长仅删除排版空格。', 'rule_id': '4648'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.leaderTab li p a[href]'):
        if not visible(link):
            continue
        parts = text(link).rsplit(' ', 1)
        if len(parts) != 2:
            raise ValueError('人物导航分隔边界变化')
        duty = re.sub(r'\s+', '', parts[0])
        name = parts[1]
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise ValueError('导航姓名或职务异常')
        url = urljoin(final_url, link['href'])
        rows.append({'name': name, 'evidence': duty, 'detail_url': '' if url == final_url else url})
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
