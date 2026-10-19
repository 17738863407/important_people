from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3629","domain":"www.neu.edu.cn","page_type":"现任领导列表","structure_group":"neu_leader_list_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"list_duty_name_detail","collector":"static_http","parser":"page_neu_current_leaders_v1","leader_region_selector":".leader-list","name_selector":"li.flex .span a","duty_selector":"li.flex>p.flex","detail_link_selector":"li.flex .span a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exclude_navigation","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按领导列表顺序提取职务、姓名与详情页。"""
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for item in soup.select("li.flex"):
        d=item.select_one(":scope>p.flex");n=item.select_one(":scope>.span a");name=clean(n.get_text(" ",strip=True) if n else "");duty=clean(d.get_text(" ",strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
            href=str(n.get("href","")) if n else "";detail=urljoin(final_url,href) if href and not href.startswith(("#","javascript:","mailto:")) else ""
            if detail.rstrip("/")==final_url.rstrip("/"):detail=""
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":detail,"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；item=li.flex；fields=p.flex+.span a"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
