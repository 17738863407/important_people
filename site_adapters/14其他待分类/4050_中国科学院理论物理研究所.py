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
PAGE_RULE={"rule_id":"4050","page_type":"研究所领导卡片页","structure_group":"itp_people_list_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_itp_people_list_cards_v1","leader_region_selector":"li.people_list","name_selector":"span.name首项","duty_selector":"span.name.die","detail_link_selector":"a[href]","content_scope":{"start_anchor":"现任领导","end_anchor":"常用链接","include_selectors":["li.people_list"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_link"},"risk_flag":"所务委员与所领导均为页面明确现任领导卡片，按原顺序保留。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前6张领导卡片中的姓名、职务及真实链接。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li.people_list"},"api":{"enabled":False,"reason":"HTML直接呈现个人卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select('li.people_list a[href]'):
        name_node=card.select_one('span.name:not(.die)');duty_node=card.select_one('span.name.die');name=re.sub(r"\s+","",name_node.get_text(' ',strip=True) if name_node else '');duty=re.sub(r"\s+","",duty_node.get_text(' ',strip=True) if duty_node else '')
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":urljoin(final_url,card['href']),"evidence":duty,"parser":str(page_rule['parser']),"selector_summary":"li.people_list span.name / span.name.die"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
