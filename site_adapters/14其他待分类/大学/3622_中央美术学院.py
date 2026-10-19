from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3622","domain":"www.cafa.edu.cn","page_type":"人物详情页侧栏领导目录","structure_group":"cafa_leader_sidebar_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"sidebar_duty_name_detail","collector":"static_http","parser":"page_cafa_current_leaders_v1","leader_region_selector":"ul:has(a.cur)","name_selector":"a","duty_selector":"a","detail_link_selector":"li a[href]","detail_strategy":{"required":True,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exclude_person_biography","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip()

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """从详情页侧栏的学院领导目录提取当前领导。"""
    soup=BeautifulSoup(html,"html.parser");region=None
    for ul in soup.select("ul"):
        if any(clean(a.get_text(" ",strip=True))=="学院领导" for a in ul.select("a")):region=ul;break
    if region is None:return []
    rows=[]
    for link in region.select("li a[href]"):
        text=clean(link.get_text(" ",strip=True));match=re.fullmatch(r"(.+?)[:：]([\u4e00-\u9fff·]{2,5})",text)
        if match:
            duty,name=match.group(1).strip(),match.group(2)
            detail=urljoin(final_url,str(link.get("href","")))
            if detail.rstrip("/")==final_url.rstrip("/"):detail=""
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":detail,"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=学院领导侧栏ul；item=li a；split=职务冒号姓名"})
    return rows

def main()->None:
    """运行当前页面级在线爬虫。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
