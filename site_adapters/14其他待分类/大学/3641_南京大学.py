from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3641","domain":"www.nju.edu.cn","page_type":"现任领导职务分组","structure_group":"nju_leader_groups_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"group_title_names","collector":"static_http","parser":"page_nju_current_leaders_v1","leader_region_selector":".xdld1","name_selector":"h2.flex>p a[href]","duty_selector":"h2.flex>span","detail_link_selector":"h2.flex>p a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exclude_display_none_erroneous_news_item;merge_repeated_names","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def clean_duty(node)->str:
    text=node.get_text("；",strip=True);return re.sub(r"；+","；",re.sub(r"\s+","",text)).strip("；：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one(".xdld1");ordered=[];by_name={}
    if region is None:return []
    for group in region.select("h2.flex"):
        if "display:none" in str(group.get("style","")).replace(" ","").lower():continue
        d=group.find("span",recursive=False);names=group.find("p",recursive=False);duty=clean_duty(d) if d else ""
        if not duty or names is None:continue
        for link in names.select("a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.xdld1；group=h2.flex:not(display:none)；fields=direct span+direct p a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
