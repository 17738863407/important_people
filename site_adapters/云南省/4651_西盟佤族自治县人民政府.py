"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.zfld_layer li p a人物标题为职务+姓名，排除头像重复，DOM序及隐藏过滤；挂职括注与本条人物绑定并完整保留。', 'cleaning_note': '人物标题原文去除已独立定位的姓名，职务及其后挂职括注保留。', 'rule_id': '4651'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.zfld_layer li p a[href]'):
        if not visible(link):
            continue
        parts = text(link).split(' ', 1)
        if len(parts) != 2:
            raise ValueError('人物标题边界变化')
        match = re.fullmatch(r'([\u4e00-\u9fff·]{2,8})([（(].+[）)])?', parts[1])
        if not match:
            raise ValueError('姓名或挂职括注异常')
        rows.append({'name': match.group(1), 'evidence': parts[0] + (match.group(2) or ''), 'detail_url': urljoin(final_url, link['href'])})
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
