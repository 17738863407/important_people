"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.organization ul li a仅县长、副县长人物条目，末个全角空格分隔姓名与职务，姓名内部排版空格删除，过滤隐藏、DOM顺序。', 'cleaning_note': '原始a文本按最后全角空格切分，依据保留右侧职务原文。', 'rule_id': '4634'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.organization ul li a[href]'):
        if not visible(link):
            continue
        raw = link.get_text('', strip=True)
        parts = raw.rsplit('　', 1)
        if len(parts) != 2:
            raise ValueError('姓名职务分隔符变化')
        name = re.sub(r'\s+', '', parts[0])
        duty = parts[1].strip()
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise ValueError('姓名或职务字段异常')
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
