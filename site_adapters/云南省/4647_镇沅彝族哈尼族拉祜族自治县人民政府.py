"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.gov1领导容器，首位.gov1-ltx h3姓名与p简介末句任职证据；右侧.ldlb卡片title及.ldzw职务；排除工作职责/领导活动链接。入口县长标签与简介代理县长表述冲突需人工复核。', 'cleaning_note': '首位简介按句号分句取最后完整任职句，保留代理限定；其余.ldzw原职务字段。', 'rule_id': '4647'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    first = soup.select_one('.gov1-ltx')
    if first and visible(first):
        heading = first.select_one('h3')
        name = re.sub(r'\s+', '', ''.join(heading.find_all(string=True, recursive=False)))
        sentences = [s.strip() for s in text(first.select_one('p')).split('。') if s.strip()]
        link = first.select_one('.gov1-ld a[href]')
        if not link or len(sentences) < 2 or not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('首位领导简介结构变化')
        rows.append({'name': name, 'evidence': sentences[-1], 'detail_url': urljoin(final_url, link['href'])})
    for link in soup.select('.gov1 .ldlb li a[href]'):
        if not visible(link):
            continue
        name = re.sub(r'\s+', '', link.get('title', ''))
        duty = text(link.select_one('.ldzw'))
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
            raise ValueError('领导卡片字段异常')
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
