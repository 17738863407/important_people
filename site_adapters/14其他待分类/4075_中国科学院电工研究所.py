from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4075","page_type":"研究所领导列表页","structure_group":"iee_position_sibling_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_iee_position_sibling_v1","leader_region_selector":"div.leader li:has(span.position)","name_selector":"position后的直系文本","duty_selector":"span.position","detail_link_selector":"","content_scope":{"start_anchor":"所长、党委书记","end_anchor":"电工所概况","include_selectors":["div.leader li:has(span.position)"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅取position后的直系姓名文本，注释内助理不进入DOM。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验4个职位—姓名li。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"div.leader li:has(span.position)"},"api":{"enabled":False,"reason":"HTML列表完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for li in soup.select('div.leader li:has(span.position)'):
        v=li.select_one('.position').get_text(" ",strip=True);strings=[x.strip() for x in li.find_all(string=True,recursive=False) if x.strip()];n=re.sub(r"\s+","",strings[-1]) if strings else ''
        if 2<=len(n)<=4 and n.isalpha() and v:rows.append({"name":n,"duty":v,"detail_url":"","evidence":v,"parser":str(page_rule['parser']),"selector_summary":"领导li的position和直系姓名文本"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
