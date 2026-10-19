from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3644","domain":"www.hhu.edu.cn","page_type":"现任领导职务栏目聚合","structure_group":"hhu_leader_posts_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"post_title_names","collector":"static_http","parser":"page_hhu_current_leaders_v1","leader_region_selector":".mod","name_selector":".post .news_title a[href]","duty_selector":".post .tt .title","detail_link_selector":".post .news_title a[href]","detail_strategy":{"required":True,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"strict_post_title_boundary","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for group in soup.select(".post"):
        d=group.select_one(":scope>.tt .title");duty=clean(d.get_text(" ",strip=True) if d else "")
        if duty not in {"党委书记","校长、党委副书记","党委副书记、纪委书记","党委副书记、副校长","副校长"}:continue
        for link in group.select(":scope>.con .news_title a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":urljoin(final_url,str(link.get("href",""))),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；group=.post；fields=.tt .title+.con .news_title a"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
