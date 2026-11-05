"""当前在线页面专用技术规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {'validation_note': '.right_box0 .box0_info_box领导简介，与.detail_item .name导航逐一同序核对；v-show为人物选项卡对应数据，非模板隐藏噪声。排除分工与机构列表，无独立人物页。', 'cleaning_note': 'user_desc原文限定现任完整句，删除句首现任与句末句号。', 'rule_id': '4635'}

def visible(node):
    return not any(p.has_attr('hidden') or p.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', p.get('style', ''), re.I) for p in [node, *node.parents] if getattr(p, 'attrs', None) is not None)

def text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip() if node else ''

def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for card in soup.select('.right_box0 .box0_info_box'):
        if not visible(card):
            continue
        name = re.sub(r'\s+', '', text(card.select_one('.user_name')))
        raw = text(card.select_one('.user_desc'))
        match = re.search(r'现任([^。]+)', raw)
        if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name) or not match:
            raise ValueError('领导简介现职证据缺失')
        rows.append({'name': name, 'evidence': match.group(1).strip(), 'detail_url': ''})
    navigation = [re.sub(r'\s+', '', text(n)) for n in soup.select('.detail_item .name')]
    if navigation != [r['name'] for r in rows]:
        raise ValueError('人物导航与简介顺序不一致')
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
