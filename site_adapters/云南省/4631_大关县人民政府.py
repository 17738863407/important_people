"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '入口.function-itme内.function-txt与头像链接，详情限定.szcharin简介取完整现任句，排除分工.szcharin2；逐项HTTP，DOM顺序，隐藏过滤。', 'cleaning_note': '详情.szcharin原文定位现任…完整句，删除现任及句末句号，其余保留。原文存同次详情响应。', 'rule_id': '4631'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import requests
    rows = []
    for card in soup.select('.function-itme'):
        if not visible(card):
            continue
        name = re.sub(r'\s+', '', text(card.select_one('.function-txt')))
        link = card.select_one('.function-img a[href]')
        if not link or not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('领导卡片异常')
        url = urljoin(final_url, link['href'])
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, 'html.parser')
        raw = text(detail.select_one('.szcharin'))
        match = re.search(r'现任([^。]+)', raw)
        if name not in re.sub(r'\s+', '', raw) or not match:
            raise ValueError('个人详情缺少可回指现职句')
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
