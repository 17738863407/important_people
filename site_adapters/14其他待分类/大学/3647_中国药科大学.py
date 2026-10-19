from __future__ import annotations
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3647","domain":"www.cpu.edu.cn","page_type":"党政领导四列表格","structure_group":"cpu_leader_table_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"paired_duty_names_text","collector":"static_http","parser":"page_cpu_current_leaders_v1","leader_region_selector":"table.wp_editor_art_table","name_selector":"td","duty_selector":"td","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"names_are_plain_text_with_layout_spaces","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "")).strip("：:")

def extract_names(cell)->list[str]:
    """页面以四个以上排版空白分隔姓名，三空白用于双字姓名字间距。"""
    names=[]
    for chunk in cell.stripped_strings:
        for part in re.split(r"\s{4,}",str(chunk)):
            name=clean(part)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):names.append(name)
    return names

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");table=None;allowed={"党委书记","校长","党委副书记","副校长","纪委书记","党委常委","校长助理"}
    for candidate in soup.select("table.wp_editor_art_table"):
        text=clean(candidate.get_text(" ",strip=True))
        if all(key in text for key in ("党委书记","纪委书记","校长助理")):table=candidate;break
    if table is None:return []
    ordered=[];by_name={}
    for tr in table.select("tbody>tr"):
        cells=tr.find_all("td",recursive=False)
        for i in range(0,len(cells)-1,2):
            duty=clean(cells[i].get_text(" ",strip=True))
            if duty not in allowed:continue
            for name in extract_names(cells[i+1]):
                if name not in by_name:by_name[name]=[];ordered.append(name)
                if duty not in by_name[name]:by_name[name].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]),"evidence":"；".join(by_name[name]),"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=含党委书记/纪委书记/校长助理table；pairs=td；name_separator=4+layout_spaces"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
