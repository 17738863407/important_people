from __future__ import annotations
import sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4069","page_type":"研究所领导卡片页","structure_group":"genetics_two_name_p_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_genetics_two_name_p_v1","leader_region_selector":"li:has(a>p.name:nth-of-type(2))","name_selector":"a>p.name:first-of-type","duty_selector":"a>p.name:nth-of-type(2)","detail_link_selector":"a[href]","content_scope":{"start_anchor":"现任领导","end_anchor":"联系我们","include_selectors":["li:has(a>p.name:nth-of-type(2))"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"card_link"},"risk_flag":"卡片第二个name段为职务字段。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验7张双name卡片。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li:has(a>p.name:nth-of-type(2))"},"api":{"enabled":False,"reason":"HTML卡片完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for li in soup.select("li:has(p.name:nth-of-type(2))"):
        a=li.select_one('a[href]');ps=li.select('p.name')
        if len(ps)>=2:
            n,v=ps[0].get_text(" ",strip=True),ps[1].get_text(" ",strip=True)
            if 2<=len(n)<=4 and n.isalpha() and v:rows.append({"name":n,"duty":v,"detail_url":a['href'] if a else "","evidence":v,"parser":str(page_rule["parser"]),"selector_summary":"领导卡片双name段"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
