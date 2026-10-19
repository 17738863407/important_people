from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3633","domain":"www.fudan.edu.cn","page_type":"党委行政领导表格","structure_group":"fudan_governance_leaders_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"two_tables_rowspan","collector":"static_http","parser":"page_fudan_current_leaders_v1","leader_region_selector":"#wp_content_w6_0","name_selector":"table a[href]","duty_selector":"table strong","detail_link_selector":"table a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"strictly_exclude_committee_rosters_after_administrative_table","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """仅解析党委领导、行政领导两张表，并处理跨行职务单元格。"""
    soup=BeautifulSoup(html,"html.parser");ordered=[];by_name={}
    for section_title in ("党委领导","行政领导"):
        heading=next((h for h in soup.select("#wp_content_w6_0 h3") if clean(h.get_text(" ",strip=True))==section_title),None)
        table=heading.find_next_sibling("table") if heading else None
        if table is None:continue
        current_duty=""
        for tr in table.select("tbody tr"):
            cells=tr.find_all("td",recursive=False)
            if not cells:continue
            duty_cell=cells[0] if cells[0].find("strong") else None
            if duty_cell is not None:current_duty=clean(duty_cell.get_text(" ",strip=True));name_cells=cells[1:]
            else:name_cells=cells
            if not current_duty:continue
            for cell in name_cells:
                for link in cell.select("a[href]"):
                    name=clean(link.get_text(" ",strip=True))
                    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
                    if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
                    if current_duty not in by_name[name]["duties"]:by_name[name]["duties"].append(current_duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=#wp_content_w6_0；tables=党委领导+行政领导；rowspan_carry=true"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
