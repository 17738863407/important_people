from __future__ import annotations
import sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4175','page_type':'现任所领导页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_bjs_leader_cards_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 lines=list(BeautifulSoup(html,'html.parser').stripped_strings);start=max((i for i,x in enumerate(lines) if x=='现任所领导'),default=None)
 if start is None:return []
 rows=[]
 for i in range(start+1,len(lines)-1):
  n=''.join(lines[i].split());d=lines[i+1].strip()
  if 2<=len(n)<=4 and all('\u4e00'<=c<='\u9fff' for c in n) and any(x in d for x in ('书记','所长')):rows.append({'name':n,'duty':d,'evidence':d,'detail_url':''})
  if i>start+15:break
 return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
