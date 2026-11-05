"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': 'u_u6_title/id为当前页真实渲染数组，隐藏a仅存储渲染链接；按数组顺序逐详情.v_news_content职务标签段取证，同名简介回指，排除分工。', 'cleaning_note': '删除个人页职务：或职务:字段前缀，姓名与简历如紧随字段则按精确姓名边界排除。', 'rule_id': '4667'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import json
    import requests
    arrays = {}
    for field in ('title', 'id'):
        match = re.search(r'var\s+u_u6_' + field + r'\s*=\s*(\[[^;]*\])\s*;', html)
        if not match:
            raise ValueError('渲染数组缺失')
        arrays[field] = json.loads(match.group(1))
    if len(arrays['title']) != len(arrays['id']):
        raise ValueError('人物数组长度不一致')
    rows = []
    for name, identifier in zip(arrays['title'], arrays['id']):
        link = soup.find('a', id='u_u6_' + identifier + '_a')
        if not link or not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('人物索引异常')
        url = urljoin(final_url, link['href'])
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, 'html.parser')
        content = detail.select_one('.v_news_content')
        fields = [text(p) for p in content.select('p') if re.match(r'^职务[：:]', text(p))] if content else []
        if len(fields) != 1 or name not in re.sub(r'\s+', '', text(content)):
            raise ValueError('个人页职务标签或姓名证据不足')
        duty = re.sub(r'^职务[：:]\s*', '', fields[0]).split(name, 1)[0].strip()
        if not duty:
            raise ValueError('职务字段为空')
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
