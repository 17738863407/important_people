from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3639","domain":"www.shisu.edu.cn","page_type":"职务标题多人表格","structure_group":"shisu_leader_table_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"table_title_names","collector":"static_http","parser":"page_shisu_current_leaders_v1","leader_region_selector":"table","name_selector":"td:nth-of-type(2) a[href]","duty_selector":"td:nth-of-type(1)","detail_link_selector":"td:nth-of-type(2) a[href]","detail_strategy":{"required":True,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"merge_repeated_names_across_titles","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");table=None
    for candidate in soup.select("table"):
        text=clean(candidate.get_text(" ",strip=True))
        if all(key in text for key in ("党委书记","纪委书记","党委常委")):table=candidate;break
    if table is None:return []
    ordered=[];by_name={}
    for tr in table.select("tbody>tr"):
        cells=tr.find_all("td",recursive=False)
        if len(cells)<2:continue
        duty=clean(cells[0].get_text(" ",strip=True))
        for link in cells[1].select("a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=含党委书记/纪委书记/常委table；row=tbody>tr；fields=td[0]+td[1]a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
