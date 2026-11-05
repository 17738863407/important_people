"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '当前.list-nav仅8个政府领导个人导航，姓名及括注职务显式同项，混合中英文括号兼容，保持导航DOM序；当前县长页等于依据链接故详情留空。', 'cleaning_note': '导航原文以括号边界拆分姓名与原始职务，去除外围括号，保留全部职务文字。', 'rule_id': '4643'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for link in soup.select('.list-nav > li > a[href]'):
        if not visible(link):
            continue
        match = re.fullmatch(r'(.+?)[（(](.+)[）)]', text(link))
        if not match:
            raise ValueError('领导导航姓名职务结构变化')
        name = re.sub(r'\s+', '', match.group(1))
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('领导姓名异常')
        url = urljoin(final_url, link['href'])
        rows.append({'name': name, 'evidence': match.group(2), 'detail_url': '' if url == final_url else url})
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
