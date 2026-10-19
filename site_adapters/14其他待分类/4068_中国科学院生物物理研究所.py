from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4068","page_type":"研究所领导卡片页","structure_group":"ibp_info_s_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ibp_info_s_v1","leader_region_selector":"div.info-s:has(.name-s):has(.job-s)","name_selector":".name-s","duty_selector":".job-s","detail_link_selector":".name-s[href$='.html']","content_scope":{"start_anchor":"现任领导","end_anchor":"版权所有","include_selectors":["div.info-s:has(.name-s):has(.job-s)"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"card_link"},"risk_flag":"所务委员兼部门职务均为页面明确现职，按卡片顺序保留。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验10张姓名—职务卡片。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"div.info-s:has(.name-s):has(.job-s)"},"api":{"enabled":False,"reason":"HTML卡片完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for c in soup.select("div.info-s:has(.name-s):has(.job-s)"):
        a=c.select_one('.name-s[href]');v=c.select_one('.job-s').get_text(" ",strip=True)
        if a:
            n=a.get_text(" ",strip=True)
            if 2<=len(n)<=4 and n.isalpha() and v:rows.append({"name":n,"duty":v,"detail_url":urljoin(final_url,a['href']),"evidence":v,"parser":str(page_rule["parser"]),"selector_summary":"领导info-s卡片name-s与job-s"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
