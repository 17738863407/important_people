from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3642","domain":"www.seu.edu.cn","page_type":"现任领导职务分组列表","structure_group":"seu_leader_groups_2026","reuse_scope":"single_page","load_mode":"动态DOM渲染","force_browser":True,"fetch_mode":"online","extract_mode":"dl_title_names","collector":"playwright","parser":"page_seu_current_leaders_v1","leader_region_selector":"#wp_content_w6_0","name_selector":".news_box dl dt a[href]","duty_selector":".news_box dl dt.list_head","detail_link_selector":".news_box dl dt a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"http_403_requires_browser;merge_repeated_names","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def clean_duty(node)->str:
    return re.sub(r"；+","；",re.sub(r"\s+","",node.get_text("；",strip=True))).strip("；：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one("#wp_content_w6_0");ordered=[];by_name={}
    if region is None:return []
    for group in region.select(".news_box dl"):
        head=group.select_one("dt.list_head");duty=clean_duty(head) if head else ""
        for link in group.select("dt:not(.list_head) a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=#wp_content_w6_0；group=.news_box dl；fields=dt.list_head+dt a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
