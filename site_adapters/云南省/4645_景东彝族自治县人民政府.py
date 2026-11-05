"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.fileName li.fileShi1领导卡片，.details h4 a姓名，限定本卡片.fileDetails或.fileDetails1完整现任句，排除独立分工片段，DOM序及隐藏过滤。', 'cleaning_note': '简介原文中定位现任完整句，按句界或，负责/，主管/，中共党员字段边界裁剪，保留全部现任职务，原文在同次响应。', 'rule_id': '4645'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for card in soup.select('.fileName li.fileShi1'):
        if not visible(card):
            continue
        link = card.select_one('.details h4 a[href]')
        name = re.sub(r'[\s\u200b\ufeff]+', '', text(link))
        raw = text(card.select_one('.fileDetails, .fileDetails1'))
        match = re.search(r'现任([^。]+)', raw)
        duty = re.split(r'，(?:负责|主管|中共党员)', match.group(1), maxsplit=1)[0] if match else text(card.select_one('.position, .position1'))
        if not link or not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
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
