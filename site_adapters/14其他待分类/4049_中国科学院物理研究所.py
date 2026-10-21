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
PAGE_RULE={"rule_id":"4049","page_type":"研究所领导链接卡片页","structure_group":"iop_leader_link_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_iop_leader_link_cards_v1","leader_region_selector":".text-center.pb-5 a","name_selector":"链接末尾姓名","duty_selector":"链接姓名前职务","detail_link_selector":"a[href]","content_scope":{"start_anchor":"现任领导","end_anchor":"电子所刊","include_selectors":[".text-center.pb-5"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_link"},"risk_flag":"姓名与职务在同一实时个人链接文本，需按末尾姓名切分。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验5个现任领导链接的文本和真实详情页。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".text-center.pb-5 a"},"api":{"enabled":False,"reason":"HTML直接呈现个人链接"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for link in BeautifulSoup(html,"html.parser").select('.text-center.pb-5 a[href]'):
        matched=re.fullmatch(r"\s*(.+?)\s+([\u4e00-\u9fff·]{2,4})\s*",link.get_text(" ",strip=True))
        if matched:
            duty=re.sub(r"\s+","",matched.group(1));name=matched.group(2)
            rows.append({"name":name,"duty":duty,"detail_url":urljoin(final_url,link['href']),"evidence":duty,"parser":str(page_rule['parser']),"selector_summary":"人物卡片链接文本中的职务+姓名"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
