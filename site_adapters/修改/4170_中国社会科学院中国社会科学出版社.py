from __future__ import annotations
import re, sys
from pathlib import Path
def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'crawler_core').is_dir(): return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4170','page_type':'领导团队页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_cssp_leader_v1','leader_region_selector':'body','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str, final_url:str, page_rule:dict)->list[dict]:
 from bs4 import BeautifulSoup
 lines=list(BeautifulSoup(html,'html.parser').stripped_strings); rows=[]
 for line in lines:
  m=re.match(r'^(党委书记、社长|总编辑|副社长|副总编辑|总编辑助理)[：:]([\u4e00-\u9fff·]{2,4})$',re.sub(r'\s+','',line))
  if m: rows.append({'name':m.group(2),'duty':m.group(1),'detail_url':''})
 return rows
def main()->None:
 project_dir=resolve_project_dir();sys.path.insert(0,str(project_dir)) if str(project_dir) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__': main()
