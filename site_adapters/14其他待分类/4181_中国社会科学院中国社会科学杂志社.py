from __future__ import annotations
import sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4181','page_type':'社领导卡片页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_sscp_leaders_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 a=list(BeautifulSoup(html,'html.parser').stripped_strings);s=next(i for i,x in enumerate(a) if x=='社领导');rows=[]
 for i in range(s+1,min(s+18,len(a)-1)):
  n=''.join(a[i].split());d=a[i+1].strip()
  if 2<=len(n)<=4 and all('\u4e00'<=c<='\u9fff' for c in n) and '中国社会科学杂志社' in d and any(x in d for x in ('书记','总编辑')):rows.append({'name':n,'duty':d.replace('中国社会科学杂志社','',1).split('，',1)[0],'evidence':d,'detail_url':''})
 return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
