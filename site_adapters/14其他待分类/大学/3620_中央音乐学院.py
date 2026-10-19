from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3620","domain":"www.ccom.edu.cn","page_type":"现任领导人物卡片","structure_group":"ccom_leader_cards_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"card_name_duty_detail","collector":"static_http","parser":"page_ccom_current_leaders_v1","leader_region_selector":".leaders","name_selector":"h4","duty_selector":"h6","detail_link_selector":"a.a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exclude_navigation","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按人物卡片顺序提取姓名、职务和独立详情页。"""
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for link in soup.select("a.a[href]"):
        n=link.select_one("h4");d=link.select_one("h6");name=clean(n.get_text(" ",strip=True) if n else "");duty=clean(d.get_text(" ",strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":urljoin(final_url,str(link.get("href",""))),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；item=a.a；fields=h4+h6"})
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
