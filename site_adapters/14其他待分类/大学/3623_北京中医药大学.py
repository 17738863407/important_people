from __future__ import annotations
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3623","domain":"www.bucm.edu.cn","page_type":"现任领导人物卡片","structure_group":"bucm_leader_cards_2026","reuse_scope":"single_page","load_mode":"动态DOM渲染","force_browser":True,"fetch_mode":"online","extract_mode":"card_name_duty","collector":"playwright","parser":"page_bucm_current_leaders_v1","leader_region_selector":".page-list","name_selector":"a.item .title","duty_selector":"a.item .info","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"http_403_requires_browser","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按页面人物卡片顺序提取姓名和职务。"""
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for item in soup.select("a.item"):
        n=item.select_one(".title");d=item.select_one(".info");name=clean(n.get_text(" ",strip=True) if n else "");duty=clean(d.get_text(" ",strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；item=a.item；fields=.title+.info"})
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
