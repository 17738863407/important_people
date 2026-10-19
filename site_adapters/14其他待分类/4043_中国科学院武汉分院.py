from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4043","page_type":"分院领导卡片页","structure_group":"cas_whb_leader_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cas_whb_leader_cards_v1","leader_region_selector":"现任领导卡片li","name_selector":"p span首行","duty_selector":"p span次行","detail_link_selector":"a[href]","content_scope":{"start_anchor":"分院领导","end_anchor":"分院概况","include_selectors":["li"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_link"},"risk_flag":"卡片首行姓名、次行完整现职，详情链接来自卡片。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前四张分院领导卡片。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li a > p > span"},"api":{"enabled":False,"reason":"HTML直接呈现卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select("li a:has(p > span)"):
        span=card.select_one("p > span");parts=list(span.stripped_strings) if span else []
        if len(parts)>=2:
            name=re.sub(r"\s+","",parts[0]);duty=re.sub(r"\s+","",parts[1]);href=card.get("href","")
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":urljoin(final_url,href),"evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"现任领导卡片p>span"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
