from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3648","domain":"www.hfut.edu.cn","page_type":"现任领导职务分组","structure_group":"hfut_leader_groups_desktop_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"group_title_names","collector":"static_http","parser":"page_hfut_current_leaders_v1","leader_region_selector":"ul.ld-ul-lg","name_selector":".ld-ul-box .ld-name a[href]","duty_selector":".ld-ul-box .ld-zw","detail_link_selector":".ld-ul-box .ld-name a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exclude_duplicate_mobile_ld_ul_sm;merge_repeated_names","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one("ul.ld-ul-lg");ordered=[];by_name={}
    if region is None:return []
    for group in region.select(":scope>li>.ld-ul-box"):
        d=group.select_one(":scope>.ld-zw");duty=clean(d.get_text(" ",strip=True) if d else "")
        for link in group.select(":scope>.ld-name a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            href=str(link.get("href",""));detail=urljoin(final_url,href) if href and not href.startswith(("#","javascript:","mailto:")) else ""
            if name not in by_name:by_name[name]={"duties":[],"detail_url":detail};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=ul.ld-ul-lg；group=li>.ld-ul-box；fields=.ld-zw+.ld-name a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
