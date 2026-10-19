from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3637","domain":"web.dhu.edu.cn","page_type":"职务标题多人名单","structure_group":"dhu_legacy_leader_paragraphs","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"paragraph_title_names","collector":"static_http","parser":"page_dhu_current_leaders_v1","leader_region_selector":"#wp_content_w6_0","name_selector":"p a[href]","duty_selector":"p","detail_link_selector":"p a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"source_page_is_legacy_original_site_data","confidence":"medium","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    text=str(text or "").replace("（兼）","").replace("\u3000"," ").replace("\xa0"," ")
    return re.sub(r"\s+","",text).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """从每个职务段落的冒号前标题提取其后人物，并合并兼任。"""
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one("#wp_content_w6_0");ordered=[];by_name={}
    if region is None:return []
    for p in region.select(":scope>p"):
        full=p.get_text(" ",strip=True);match=re.match(r"\s*([^：:]+)[:：]",full)
        duty=clean(match.group(1)) if match else ""
        if not duty:continue
        for link in p.select("a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=#wp_content_w6_0；group=p职务冒号多人"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
