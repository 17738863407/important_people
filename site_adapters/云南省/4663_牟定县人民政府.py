"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '当前info/2335人物栏目非空姓名链接，逐人.v_news_content现任句，避免入口摘要截断/分工混合，DOM序及隐藏过滤。', 'cleaning_note': '限定个人正文现任句，删除现任与句末标点，保留完整职务和机构前缀。', 'rule_id': '4663'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    import requests
    rows = []
    seen = set()
    for link in soup.select('a[href*="/2335/"]'):
        if not text(link) or not visible(link):
            continue
        name = re.sub(r'\s+', '', text(link))
        url = urljoin(final_url, link['href'])
        if url in seen:
            continue
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
            raise ValueError('领导姓名异常')
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail = BeautifulSoup(response.text, 'html.parser')
        content = detail.select_one('.v_news_content')
        raw = text(content)
        match = re.search(r'现任([^。]+)', raw)
        paragraphs = [text(p) for p in content.select('p') if text(p)] if content else []
        field_duty = paragraphs[0] if len(paragraphs) > 1 and paragraphs[1] == '领导分工：' else ''
        duty = match.group(1).strip() if match else field_duty
        if name not in re.sub(r'\s+', '', raw) or not duty:
            raise ValueError('个人页同名现职证据不足')
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
