from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
PAGE_RULE={"rule_id":"3613","domain":"www.cugb.edu.cn","page_type":"现任领导简介卡片","structure_group":"cugb_leader_items_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"card_title_bold_duty","collector":"static_http","parser":"page_cugb_current_leaders_v1","leader_region_selector":".leader-item","name_selector":".news-item-title","duty_selector":".leader-line+div b","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"exclude_biography_text","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}
def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p/"crawler_core").is_dir():return p
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def clean(t:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(t or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按现任领导卡片顺序提取姓名和卡片职务字段。"""
    s=BeautifulSoup(html,"html.parser");rows=[]
    for item in s.select(".news-item.leader-item"):
        n=item.select_one(".news-item-title");d=item.select_one(".leader-line + div b");name=clean(n.get_text(" ",strip=True) if n else "");duty=clean(d.get_text(" ",strip=True) if d else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；item=.news-item.leader-item；fields=.news-item-title+.leader-line+div b"})
    return rows
def main()->None:
    """运行当前页面级在线爬虫。"""
    p=resolve_project_dir()
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from crawler_core.runner import run_page_adapter
    c={};o=run_page_adapter(PAGE_RULE,globals(),runtime_context=c,update_fetch_memory=False);print(f"实际采集器：{c.get('actual_collector','')}");print(f"输出文件：{o}")
if __name__=="__main__":
    main()
