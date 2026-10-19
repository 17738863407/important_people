from __future__ import annotations
import re,sys
from pathlib import Path
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/'crawler_core').is_dir():return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4103','page_type':'领导卡片页','structure_group':'iue_titbox_h4_span','reuse_scope':'page_structure','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_iue_titbox_h4_span','leader_region_selector':'.titbox','risk_flag':'姓名与职务位于同一标题，按直接文本和 span 分离','confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
 from bs4 import BeautifulSoup
 s=BeautifulSoup(html,'html.parser');rows=[]
 for card in s.select('.titbox'):
  h=card.select_one('h4');span=h.select_one('span') if h else None
  if h and span:
   name=''.join(str(x).strip() for x in h.find_all(string=True,recursive=False));duty=span.get_text(' ',strip=True)
   if name and duty:rows.append({'name':re.sub(r'\s+','',name),'duty':duty,'evidence':duty})
 return rows
def main()->None:
 project_dir=resolve_project_dir()
 if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
 from crawler_core.runner import run_page_adapter
 output_path=run_page_adapter(PAGE_RULE,globals());print(f'输出文件：{output_path}')
if __name__=='__main__':main()
