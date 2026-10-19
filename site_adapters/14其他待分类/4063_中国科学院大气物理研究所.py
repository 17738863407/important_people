from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4063","page_type":"研究所领导卡片页","structure_group":"iap_leader_li_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_iap_leader_li_v1","leader_region_selector":"li.col-md-2:has(p>a):has(p span)","name_selector":"p>a","duty_selector":"p span","detail_link_selector":"p>a[href$='.html']","content_scope":{"start_anchor":"现任领导","end_anchor":"返回移动版","include_selectors":["li.col-md-2:has(p>a):has(p span)"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"card_link"},"risk_flag":"学位说明不作职务字段。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验4张卡片。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li.col-md-2:has(p>a):has(p span)"},"api":{"enabled":False,"reason":"HTML卡片完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for c in soup.select("li.col-md-2:has(p>a):has(p span)"):
        a,d=c.select_one("p>a[href]"),c.select_one("p span")
        if a and d:
            n,v=a.get_text(" ",strip=True),d.get_text(" ",strip=True)
            if 2<=len(n)<=4 and n.isalpha() and v:rows.append({"name":n,"duty":v,"detail_url":urljoin(final_url,a["href"]),"evidence":v,"parser":str(page_rule["parser"]),"selector_summary":"领导li卡片p>a+span"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
