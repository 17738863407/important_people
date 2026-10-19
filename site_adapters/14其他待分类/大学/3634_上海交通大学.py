from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3634","domain":"www.sjtu.edu.cn","page_type":"校领导及职务分组名单","structure_group":"sjtu_current_leaders_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"cards_plus_grouped_titles","collector":"static_http","parser":"page_sjtu_current_leaders_v1","leader_region_selector":".SjtuLeader","name_selector":"a[href]","duty_selector":"small,h4","detail_link_selector":"a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"merge_party_standing_committee_group","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """先取校领导卡片，再按页面后续职务组补充或合并职务。"""
    soup=BeautifulSoup(html,"html.parser");ordered=[];by_name={}
    def add(name:str,duty:str,href:str)->None:
        name,duty=clean(name),clean(duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:return
        if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,href) if href else ""};ordered.append(name)
        if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    leader_heading=next((h for h in soup.select("h4") if clean(h.get_text(" ",strip=True))=="校领导"),None)
    leader_list=leader_heading.find_next_sibling("ul") if leader_heading else None
    if leader_list:
        for item in leader_list.select(":scope>li"):
            link=item.select_one("a[href]");d=item.select_one("small")
            if link and d:add(link.get_text(" ",strip=True),d.get_text(" ",strip=True),str(link.get("href","")))
    for heading in soup.select("h4.page-title2"):
        duty=clean(heading.get_text(" ",strip=True))
        if duty not in {"党委常委","校务委员会专职副主任","校长助理","总经济师"}:continue
        group=heading.find_next_sibling("ul")
        if group:
            for link in group.select("a[href]"):add(link.get_text(" ",strip=True),duty,str(link.get("href","")))
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；primary=h4校领导+next ul；groups=h4.page-title2+next ul"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
