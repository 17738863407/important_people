"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.ldzc .brief h4分组绑定父容器非空带title人物a，隐藏过滤、DOM序；副处级领导经独立详情现职/至今字段确认，按网页原标签保留。', 'rule_id': '4640'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    seen = set()
    for heading in soup.select('.ldzc .brief h4'):
        duty = text(heading).split('：', 1)[0]
        for link in heading.parent.select('a[href][title]'):
            if not link.get('href') or not text(link) or not visible(link):
                continue
            url = urljoin(final_url, link['href'])
            if url in seen:
                continue
            name = re.sub(r'\s+', '', text(link))
            if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
                raise ValueError('人物姓名字段异常')
            seen.add(url)
            rows.append({'name': name, 'evidence': duty, 'detail_url': url})
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
