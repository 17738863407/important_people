"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '当前源u_u6_id渲染数组顺序对应隐藏链接存储节点，标题/摘要截断，逐详情.v_news_content个人简介首句姓名及现任完整句取证，不抽取下篇或导航。', 'cleaning_note': '个人正文起始简介定位姓名及现任完整句，删除现任与句末句号，排除后续独立分工段。', 'rule_id': '4662'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import json
    import requests
    match = re.search(r'var\s+u_u6_id\s*=\s*(\[[^;]*\])\s*;', html)
    if not match:
        raise ValueError('人物渲染索引数组缺失')
    rows = []
    for identifier in json.loads(match.group(1)):
        link = soup.find('a', id='u_u6_' + identifier + '_a')
        if not link:
            raise ValueError('人物索引缺少真实链接')
        url = urljoin(final_url, link['href'])
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, 'html.parser')
        content = detail.select_one('.v_news_content')
        paragraphs = [text(p) for p in content.select('p') if text(p) and visible(p)] if content else []
        raw = paragraphs[0] if paragraphs else ''
        name_match = re.match(r'^([\u4e00-\u9fff·]{2,8})[，,]', re.sub(r'\s+', '', raw))
        duty_match = re.search(r'现任([^。]+)', raw)
        if not name_match or not duty_match:
            raise ValueError('个人简介首段缺少姓名或现职句')
        rows.append({'name': name_match.group(1), 'evidence': duty_match.group(1).strip(), 'detail_url': url})
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
