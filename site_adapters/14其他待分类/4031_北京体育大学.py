from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4031","page_type":"高校现任领导卡片页","structure_group":"bsu_leader_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_bsu_leader_cards_v1","leader_region_selector":".bsu-list09 > li > .teacherList02","name_selector":"直接span","duty_selector":"直接strong","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"X","include_selectors":[".bsu-list09"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"卡片内的简介、履历和职责说明均非主职务，仅读取卡片标题字段。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验现任领导区卡片直接保存姓名和职务标题。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".bsu-list09 > li > .teacherList02"},"api":{"enabled":False,"reason":"当前HTML直接呈现卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select(".bsu-list09 > li > .teacherList02"):
        name=re.sub(r"\s+","",card.select_one(":scope > span").get_text(" ",strip=True) if card.select_one(":scope > span") else "");duty=card.select_one(":scope > strong").get_text(" ",strip=True) if card.select_one(":scope > strong") else ""
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":".bsu-list09 > li > .teacherList02"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
