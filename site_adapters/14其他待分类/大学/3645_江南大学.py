from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3645","domain":"www.jiangnan.edu.cn","page_type":"现任领导职务分组","structure_group":"jiangnan_leader_groups_2026","reuse_scope":"single_page","load_mode":"动态DOM渲染","force_browser":True,"fetch_mode":"online","extract_mode":"group_title_names","collector":"playwright","parser":"page_jiangnan_current_leaders_v1","leader_region_selector":".fl1","name_selector":".con ul.list33 a[href]","duty_selector":".con>.tit","detail_link_selector":".con ul.list33 a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"waf_requires_browser;merge_repeated_names","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one(".fl1");ordered=[];by_name={}
    if region is None:return []
    for group in region.select(".con.flex"):
        d=group.select_one(":scope>.tit");duty=clean(d.get_text(" ",strip=True) if d else "")
        for link in group.select(":scope>ul.list33 a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.fl1；group=.con.flex；fields=.tit+ul.list33 a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
