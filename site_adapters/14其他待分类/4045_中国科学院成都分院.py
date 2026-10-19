from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4045","page_type":"分院领导卡片页","structure_group":"cas_cdb_leader_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cas_cdb_leader_cards_v1","leader_region_selector":".menu-list-02 .box-s","name_selector":"a.box-name","duty_selector":".box-txt","detail_link_selector":"a.box-name[href]","content_scope":{"start_anchor":"现任领导","end_anchor":"机构设置","include_selectors":[".menu-list-02"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_link"},"risk_flag":"入口页当前领导卡片职务分为两行，按同卡片顺序合并。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验入口实际领导卡片和真实个人链接。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".menu-list-02 .box-s"},"api":{"enabled":False,"reason":"HTML直接呈现卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select(".menu-list-02 .box-s"):
        link=card.select_one("a.box-name[href]");duty_node=card.select_one(".box-txt");name=re.sub(r"\s+","",link.get_text(" ",strip=True) if link else "");duty="；".join(re.sub(r"\s+","",part) for part in duty_node.stripped_strings) if duty_node else ""
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":urljoin(final_url,urlsplit(link['href']).path),"evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":".menu-list-02 .box-s"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
