"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '正文ul.timeed li a[title]10个人物，逐详情.v_news_content同名现任句取证，DOM序；正文名单与侧栏不一致，需人工复核。', 'cleaning_note': '个人正文限定现任完整句，删除现任及句末句号，保留全部现任职务。', 'rule_id': '4650'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import requests
    rows = []
    for link in soup.select('ul.timeed li a[href][title]'):
        if not visible(link):
            continue
        name = re.sub(r'\s+', '', link['title'])
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('姓名字段异常')
        url = urljoin(final_url, link['href'])
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, 'html.parser')
        raw = text(detail.select_one('.v_news_content'))
        match = re.search(r'现任([^。]+)', raw)
        if name not in re.sub(r'\s+', '', raw) or not match:
            raise ValueError('人物详情现职证据不足')
        rows.append({'name': name, 'evidence': match.group(1).strip(), 'detail_url': url})
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
