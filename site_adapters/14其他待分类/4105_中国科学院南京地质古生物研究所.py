from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/'crawler_core').is_dir():return parent
    raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4105','page_type':'领导简介页','structure_group':'nigpas_name_duty_strong','reuse_scope':'page_structure','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_nigpas_name_duty_strong','leader_region_selector':'.TRS_Editor','risk_flag':'每人简介很长，依据说明仅取姓名职务行','confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
 from bs4 import BeautifulSoup
 s=BeautifulSoup(html,'html.parser');rows=[]
 for n in s.find_all('strong'):
  text=re.sub(r'\s+','',n.get_text(' ',strip=True));m=re.search(r'姓名：?(?P<name>[\u4e00-\u9fff]{2,4}).*?职务：?(?P<duty>.+)',text)
  link=n.select_one('a[href]')
  if m:rows.append({'name':m['name'],'duty':m['duty'],'evidence':m['duty'],'detail_url':urljoin(final_url,link['href']) if link else ''})
 return rows
def main()->None:
 project_dir=resolve_project_dir()
 if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
 from crawler_core.runner import run_page_adapter
 output_path=run_page_adapter(PAGE_RULE,globals());print(f'输出文件：{output_path}')
if __name__=='__main__':main()
