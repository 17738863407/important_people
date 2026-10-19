from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3630","domain":"www.jlu.edu.cn","page_type":"领导机构人员文章列表","structure_group":"jlu_leader_article_list_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"link_duty_colon_name","collector":"static_http","parser":"page_jlu_current_leaders_v1","leader_region_selector":"ul","name_selector":"li a","duty_selector":"li a","detail_link_selector":"li a[href]","detail_strategy":{"required":True,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"page_order_is_publish_date_order","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip()

def split_item(text:str):
    """拆分页面明确的“职务：姓名”标题。"""
    match=re.fullmatch(r"(.+?)[:：]([\u4e00-\u9fff·]{2,5})",clean(text))
    return (match.group(1).strip(),match.group(2)) if match else None

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """选择包含最多有效领导标题的列表，继承网页文章顺序。"""
    soup=BeautifulSoup(html,"html.parser");regions=[]
    for ul in soup.select("ul"):
        count=sum(1 for link in ul.select(":scope>li>a[href]") if split_item(link.get_text(" ",strip=True)))
        if count:regions.append((count,ul))
    if not regions:return []
    region=max(regions,key=lambda item:item[0])[1];rows=[]
    for link in region.select(":scope>li>a[href]"):
        parsed=split_item(link.get_text(" ",strip=True))
        if parsed:
            duty,name=parsed;rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":urljoin(final_url,str(link.get("href",""))),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=有效职务冒号姓名最多的ul；item=li>a"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
