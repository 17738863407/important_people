"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '当前源HTML内u_u6_title/summary/id三个JSON数组由同一渲染代码按索引生成领导卡片；隐藏a仅为渲染代码读取链接的存储节点，按数组索引匹配，非隐藏人物噪声。六人顺序继承源数组。', 'rule_id': '4661'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import json
    arrays = {}
    for field in ('title', 'summary', 'id'):
        match = re.search(r'var\s+u_u6_' + field + r'\s*=\s*(\[[^;]*\])\s*;', html)
        if not match:
            raise ValueError('人物渲染数组缺失')
        arrays[field] = json.loads(match.group(1))
    if not len(arrays['title']) == len(arrays['summary']) == len(arrays['id']):
        raise ValueError('人物数组长度不一致')
    rows = []
    for name, duty, identifier in zip(arrays['title'], arrays['summary'], arrays['id']):
        link = soup.find('a', id='u_u6_' + identifier + '_a')
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not duty or not link:
            raise ValueError('人物数组或对应链接异常')
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
