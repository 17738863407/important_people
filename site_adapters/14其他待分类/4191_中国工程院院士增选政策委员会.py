from __future__ import annotations
import re,sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4191','page_type':'专门委员会介绍页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_cae_special_committee_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 a=list(BeautifulSoup(html,'html.parser').stripped_strings);key=page_rule['organization'].removeprefix('中国工程院');s=next(i for i,x in enumerate(a) if key in x and '第' in x);e=next((i for i in range(s+1,len(a)) if '委员' in a[i]),len(a));rows=[]
 for x in a[s+1:e]:
  m=re.match(r'^(主任|副主任)[：:]([^\n]+)$',re.sub(r'\s+','',x))
  if m:
   for n in re.findall(r'[\u4e00-\u9fff·]{2,4}',re.sub(r'[（(][^）)]*[）)]','',m.group(2))):rows.append({'name':n,'duty':m.group(1),'evidence':x,'detail_url':''})
 return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
