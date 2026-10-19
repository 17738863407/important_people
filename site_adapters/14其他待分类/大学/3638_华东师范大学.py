from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3638","domain":"www.ecnu.edu.cn","page_type":"党政领导四列表格","structure_group":"ecnu_leader_table_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"paired_duty_names","collector":"static_http","parser":"page_ecnu_current_leaders_v1","leader_region_selector":"table","name_selector":"td a","duty_selector":"td","detail_link_selector":"td a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"stop_before_previous_leaders_links;merge_repeated_names","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """解析职务—姓名成对单元格，遇历任入口即停止。"""
    soup=BeautifulSoup(html,"html.parser");table=None
    for candidate in soup.select("table"):
        text=clean(candidate.get_text(" ",strip=True))
        if "党委书记" in text and "校长助理" in text and "历任校党委书记" in text:table=candidate;break
    if table is None:return []
    ordered=[];by_name={}
    for tr in table.select("tr"):
        cells=tr.find_all("td",recursive=False)
        if "历任校党委书记" in tr.get_text(" ",strip=True):break
        for i in range(0,len(cells)-1,2):
            duty=clean(cells[i].get_text(" ",strip=True))
            if not duty:continue
            for link in cells[i+1].select("a"):
                name=clean(link.get_text(" ",strip=True))
                if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
                href=str(link.get("href",""));detail=urljoin(final_url,href) if href and not href.startswith("#") else ""
                if name not in by_name:by_name[name]={"duties":[],"detail_url":detail};ordered.append(name)
                if not by_name[name]["detail_url"] and detail:by_name[name]["detail_url"]=detail
                if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=含党政领导及历任入口table；pairs=td[0:1]+td[2:3]"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
