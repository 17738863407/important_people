from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3636","domain":"www.ecust.edu.cn","page_type":"现任领导弹层简介卡片","structure_group":"ecust_leader_overlay_cards_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"card_name_current_title_detail","collector":"static_http","parser":"page_ecust_current_leaders_v1","leader_region_selector":"ul.news_list","name_selector":"li.news .cols_name","duty_selector":"li.news .cols_poster","detail_link_selector":"li.news .news_title a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"deduplicate_repeated_category_cards;exclude_biography","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u200b","").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """读取卡片明确的当前职务字段，并按首次出现顺序去重。"""
    soup=BeautifulSoup(html,"html.parser");ordered=[];by_name={}
    for item in soup.select("ul.news_list li.news"):
        n=item.select_one(".cols_name");d=item.select_one(".cols_poster");link=item.select_one(".news_title a[href]")
        name=clean(n.get_text(" ",strip=True) if n else "");duty=clean(d.get_text(" ",strip=True) if d else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
        if name not in by_name:by_name[name]={"duties":[],"detail_url":urljoin(final_url,str(link.get("href",""))) if link else ""};ordered.append(name)
        if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；item=ul.news_list li.news；fields=.cols_name+.cols_poster+.news_title a"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
