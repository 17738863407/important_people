from __future__ import annotations
import re,sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4014","page_type":"协会现任领导列表页","structure_group":"nafmii_leader_list","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_nafmii_leader_list_v1","leader_region_selector":".yh_leaderBox","name_selector":".yh_leaderC li a直接文本","duty_selector":".yh_leaderC li span","detail_link_selector":"","content_scope":{"start_anchor":"协会现任领导","end_anchor":"组织机构","include_selectors":[".yh_leaderBox"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"公共采集响应未包含领导卡片；内置原始HTTP采集后严格限定现任领导区域。","confidence":"high","profile_reusable":False,"profile_judgement":"领导列表卡片包含姓名与完整职务证据。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","locator":{"css":{"leader_region_selector":".yh_leaderBox","name_selector":".yh_leaderC li a","duty_selector":"span"},"api":{"enabled":False,"reason":"HTML列表完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+","",v or "").strip()
def fetch_live_html(url:str)->str:
    """实时读取包含现任领导卡片的原始HTML。"""
    session=requests.Session();session.trust_env=False
    response=session.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=30)
    response.raise_for_status();response.encoding=response.apparent_encoding
    return response.text
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    if not html:html=fetch_live_html(str(page_rule["url"]))
    root=BeautifulSoup(html,"html.parser").select_one(".yh_leaderBox");rows=[]
    for card in root.select(".yh_leaderC li") if root else []:
        a=card.select_one("a");span=card.select_one("span");name=clean("".join(a.find_all(string=True,recursive=False))) if a else "";duty=clean(span.get_text(" ",strip=True)) if span else ""
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":".yh_leaderC li 姓名+span职务"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
