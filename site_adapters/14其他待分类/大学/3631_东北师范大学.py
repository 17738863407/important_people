from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3631","domain":"www.nenu.edu.cn","page_type":"党政纪委职务分组名单","structure_group":"nenu_grouped_leaders_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"section_group_names","collector":"static_http","parser":"page_nenu_current_leaders_v1","leader_region_selector":".con","name_selector":".list19 a.a","duty_selector":".list19Box>.tit","detail_link_selector":".list19 a.a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"merge_repeated_names_across_sections","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按党委、行政、纪委分组顺序提取，并合并同一人物的多项现职。"""
    soup=BeautifulSoup(html,"html.parser");ordered=[];by_name={}
    for section in soup.select(".con"):
        header=section.select_one(":scope>h3.h3-2");section_name=clean(header.get_text(" ",strip=True) if header else "")
        if section_name not in {"党委","行政","纪委"}:continue
        for group in section.select(":scope>.list19Box"):
            title=group.select_one(":scope>.tit");base=clean(title.get_text(" ",strip=True) if title else "")
            duty=(section_name+base) if section_name in {"党委","纪委"} else base
            for link in group.select(":scope>ul.list19 a.a[href]"):
                name=clean(link.get_text(" ",strip=True))
                if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
                if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
                if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；section=.con[h3=党委/行政/纪委]；group=.list19Box；fields=.tit+ul a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
