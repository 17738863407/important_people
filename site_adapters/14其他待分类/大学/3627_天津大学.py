from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3627","domain":"www.tju.edu.cn","page_type":"现任领导列表","structure_group":"tju_leader_list_2026","reuse_scope":"single_page","load_mode":"动态DOM渲染","force_browser":True,"fetch_mode":"online","extract_mode":"list_duty_name_detail","collector":"playwright","parser":"page_tju_current_leaders_v1","leader_region_selector":".ny-main","name_selector":"li>div>a","duty_selector":"li>h3","detail_link_selector":"li>div>a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"redirect_loop_under_requests","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_name(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip()

def clean_duty(text:str)->str:
    """页面以空白分隔并列职务，统一转为全角分号。"""
    return re.sub(r"；+","；",re.sub(r"\s+","；",str(text or "").strip())).strip("；：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """定位含党委书记人物项的最小领导列表并逐项提取。"""
    soup=BeautifulSoup(html,"html.parser");region=None
    for ul in soup.select("ul"):
        if any(clean_duty(h.get_text(" ",strip=True))=="党委书记" for h in ul.select(":scope>li>h3")):region=ul;break
    if region is None:return []
    rows=[]
    for item in region.select(":scope>li"):
        n=item.select_one(":scope>div>a");d=item.select_one(":scope>h3");name=clean_name(n.get_text(" ",strip=True) if n else "");duty=clean_duty(d.get_text(" ",strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
            href=str(n.get("href","")) if n else "";detail=urljoin(final_url,href) if href and not href.startswith("#") else ""
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":detail,"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=含党委书记项ul；item=:scope>li；fields=h3+div>a"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
