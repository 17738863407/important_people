"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '正文.govnewslista252466 li a[title]共9条，title排除日期span；按正文顺序，侧栏次序不同不采用，保留挂职括注，隐藏过滤。', 'cleaning_note': '原始title按姓名后空白或姓名后的成对括号拆分；副县长（挂职）的限定完整保留。', 'rule_id': '4644'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.govnewslista252466 li a[title][href]'):
        if not visible(link):
            continue
        raw = re.sub(r'\s+', ' ', link['title']).strip()
        match = re.fullmatch(r'([^ （(]+)[（(](.+)[）)]', raw)
        parts = (match.group(1), match.group(2)) if match else raw.rsplit(' ', 1)
        if len(parts) != 2:
            raise ValueError('姓名职务标题边界变化')
        name = re.sub(r'\s+', '', parts[0])
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('姓名字段异常')
        rows.append({'name': name, 'evidence': parts[1], 'detail_url': urljoin(final_url, link['href'])})
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
