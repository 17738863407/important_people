from __future__ import annotations
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3650","domain":"www.xmu.edu.cn","page_type":"现任领导四列表格","structure_group":"xmu_leader_table_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"paired_groups_with_carry","collector":"static_http","parser":"page_xmu_current_leaders_v1","leader_region_selector":"table.table-bordered","name_selector":".leader-name","duty_selector":"td>font","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"profile_links_are_same_page_anchors;carry_blank_continuation_rows","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """解析左右职务对，并让空白续行继承同列上一职务。"""
    soup=BeautifulSoup(html,"html.parser");table=None
    for candidate in soup.select("table.table-bordered"):
        text=clean(candidate.get_text(" ",strip=True))
        if all(key in text for key in ("党委书记","党委常委","校长助理")):table=candidate;break
    if table is None:return []
    current=["",""];ordered=[];by_name={}
    def add_cell(cell,duty:str)->None:
        for node in cell.select(".leader-name"):
            name=clean(node.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            if name not in by_name:by_name[name]=[];ordered.append(name)
            if duty not in by_name[name]:by_name[name].append(duty)
    for tr in table.select("tbody>tr"):
        cells=tr.find_all("td",recursive=False)
        if len(cells)>=4:
            for column,(di,ni) in enumerate(((0,1),(2,3))):
                dnode=cells[di].find("font");new_duty=clean(dnode.get_text(" ",strip=True)) if dnode else ""
                if new_duty:current[column]=new_duty
                add_cell(cells[ni],current[column])
        elif len(cells)>=2:
            dnode=cells[0].find("font");new_duty=clean(dnode.get_text(" ",strip=True)) if dnode else ""
            if new_duty:current[0]=new_duty
            add_cell(cells[1],current[0])
    return [{"name":name,"duty":"；".join(by_name[name]),"evidence":"；".join(by_name[name]),"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=table.table-bordered；pairs=td[0:1]+td[2:3]；carry_blank_rows=true"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
