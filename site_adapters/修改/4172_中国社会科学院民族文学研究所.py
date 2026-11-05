from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4172','page_type':'现任领导页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_iel_leaders_v1','leader_region_selector':'.pn_125x160 dd.name','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
    """在现任领导卡片内按DOM顺序解析职务、姓名及对应详情。"""
    from bs4 import BeautifulSoup
    rows=[]
    for node in BeautifulSoup(html,'html.parser').select('.pn_125x160 dd.name'):
        if any(a.has_attr('hidden') or a.get('aria-hidden')=='true' or 'display:none' in str(a.get('style','')).replace(' ','') for a in [node,*node.parents]):
            continue
        match=re.fullmatch(r'(.{1,60})[：:]([\u3400-\u9fff·]{2,10})',re.sub(r'\s+','',node.get_text()))
        if not match:
            continue
        link=node.find_parent('a',href=True)
        href=str(link.get('href','')).strip() if link else ''
        detail=urljoin(final_url,href) if href and not href.lower().startswith(('#','javascript:','mailto:')) else ''
        rows.append({'name':match.group(2),'duty':match.group(1),'evidence':match.group(1),'detail_url':detail})
    return rows

def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
