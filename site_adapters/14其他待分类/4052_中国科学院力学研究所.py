from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4052","page_type":"研究所行政领导卡片页","structure_group":"imech_admin_leader_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_imech_admin_leader_cards_v1","leader_region_selector":"li.col-md-3:has(h4>span)","name_selector":"h4直接文本","duty_selector":"h4 span","detail_link_selector":"","content_scope":{"start_anchor":"行政领导","end_anchor":"版权所有","include_selectors":["li.col-md-3"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"页面标题为行政领导，卡片中党委书记、学术所长及所务委员均为明示条目。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前8张行政领导卡片。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li.col-md-3 h4"},"api":{"enabled":False,"reason":"HTML直接呈现卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select('li:has(h4 > span)'):
        h4=card.select_one('h4');duty=re.sub(r"\s+","",h4.select_one('span').get_text(' ',strip=True));name=re.sub(r"\s+","",''.join(h4.find_all(string=True,recursive=False)))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule['parser']),"selector_summary":"li.col-md-3 h4直接姓名 + span职务"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
