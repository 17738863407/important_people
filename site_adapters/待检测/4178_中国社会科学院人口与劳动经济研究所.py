from __future__ import annotations
import sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4178','page_type':'现任领导卡片页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_iple_leaders_v1','leader_region_selector':'.leader_infor','name_selector':'p:first-child','duty_selector':'p:nth-child(2)','detail_link_selector':'a[href]','detail_strategy':{'required':True,'mode':'dynamic_link'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 from urllib.parse import urljoin
 soup=BeautifulSoup(html,'html.parser');rows=[]
 for link in soup.select('a[href]'):
  region=link.select_one('.leader_infor')
  if region is None:continue
  paragraphs=region.find_all('p',recursive=False)
  if len(paragraphs)<2:continue
  n=''.join(paragraphs[0].get_text(' ',strip=True).split())
  d=''.join(paragraphs[1].get_text(' ',strip=True).split())
  if 2<=len(n)<=4 and all('\u4e00'<=c<='\u9fff' for c in n) and d.startswith('职务：'):
   rows.append({'name':n,'duty':d[3:],'detail_url':urljoin(final_url,link['href'])})
 return rows
def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
