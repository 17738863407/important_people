from __future__ import annotations
import sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4200','page_type':'部门领导页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_drc_department_leaders_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'inline_parser_handles_fetch':True,'inline_fetch_collector':'raw_http','confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 if not html:
  from crawler_core.fetcher import fetch_by_raw_requests
  html=fetch_by_raw_requests(str(page_rule['url'])).html
 a=list(BeautifulSoup(html,'html.parser').stripped_strings);s=next(i for i,x in enumerate(a) if x=='部门领导及局级干部');e=next(i for i in range(s+1,len(a)) if a[i]=='部门其他人员');rows=[];duty=''
 for x in a[s+1:e]:
  compact=''.join(x.split())
  if any(k in compact for k in ('部长','巡视员')):duty=compact;continue
  if duty and 2<=len(compact)<=4 and all('\u4e00'<=c<='\u9fff' for c in compact):rows.append({'name':compact,'duty':duty,'evidence':duty,'detail_url':''})
 return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
