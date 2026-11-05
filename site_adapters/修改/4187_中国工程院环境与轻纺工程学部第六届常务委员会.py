from __future__ import annotations
import re,sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4187','page_type':'学部常委会公示页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_cae_committee_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
    """限定目标学部标题至下一标题，完整保留跨段委员名单及多职务。"""
    from bs4 import BeautifulSoup

    root = BeautifulSoup(html, 'html.parser').select_one('#zoom')
    if root is None:
        raise RuntimeError('未找到学部常委会正文#zoom')
    target = re.sub(r'\s+', '', page_rule['organization'].removeprefix('中国工程院'))
    active = False
    duty = ''
    rows = []
    by_name = {}
    for node in root.find_all('p', recursive=False):
        if node.has_attr('hidden') or node.get('aria-hidden') == 'true' or re.search(r'display\s*:\s*none', str(node.get('style', '')), re.I):
            continue
        text = re.sub(r'\s+', '', node.get_text(' ', strip=True))
        if text == target:
            active = True
            continue
        if not active:
            continue
        if text.endswith('常务委员会'):
            break
        match = re.match(r'^(主任|副主任|委员)[：:](.*)$', text)
        if match:
            duty, text = match.groups()
        elif duty != '委员':
            continue
        text = re.sub(r'[（(][^）)]*[）)]', '', text)
        for name in re.split(r'[、，,；;]', text):
            if not re.fullmatch(r'[\u4e00-\u9fff·]{2,8}', name):
                continue
            if name in by_name:
                record = by_name[name]
                if duty not in record['duty'].split('；'):
                    record['duty'] += '；' + duty
                    record['evidence'] = record['duty']
            else:
                record = {'name': name, 'duty': duty, 'evidence': duty, 'detail_url': ''}
                rows.append(record)
                by_name[name] = record
    if not rows:
        raise RuntimeError('目标学部当前名单为空或标题未匹配')
    return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
