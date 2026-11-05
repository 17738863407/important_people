"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.zfld_layer分组.label职务、li p a姓名，隐藏的空常务副县长分组跳过，排除图片重复链接，DOM序。HTTP入口跳转HTTPS需证书兼容重试。', 'rule_id': '4646'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for group in soup.select('.zfld_layer'):
        if not visible(group):
            continue
        duty = text(group.select_one('.label'))
        for link in group.select('li p a[href]'):
            if not visible(link):
                continue
            name = re.sub(r'\s+', '', text(link))
            if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty:
                raise ValueError('人物字段异常')
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
