from __future__ import annotations
import sys
from pathlib import Path
def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir(): return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4171','page_type':'现任领导卡片页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_nacm_leader_cards_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 lines=list(BeautifulSoup(html,'html.parser').stripped_strings); start=next((i for i,x in enumerate(lines) if x=='现任领导' and i>20),None)
 if start is None:return []
 rows=[]
 for i in range(start+1,len(lines)-1):
  name,duty=lines[i].strip(),lines[i+1].strip()
  if 2<=len(name)<=4 and all('\u4e00'<=c<='\u9fff' for c in name) and any(x in duty for x in ('书记','院长')): rows.append({'name':name,'duty':duty,'evidence':duty,'detail_url':''})
 return rows
def main()->None:
 project_dir=resolve_project_dir()
 if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
