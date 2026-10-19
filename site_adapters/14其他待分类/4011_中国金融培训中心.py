from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4011","page_type":"培训中心简介正文页","structure_group":"chinacft_leaders_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_chinacft_leaders_text_v1","leader_region_selector":"正文","name_selector":"培训中心领导职务：名单","duty_selector":"主任、副主任标签","detail_link_selector":"","content_scope":{"start_anchor":"培训中心领导","end_anchor":"内设机构","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅当前领导小节。","confidence":"high","profile_reusable":False,"profile_judgement":"职务标签和名单在当前简介正文内。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");heading=soup.find("p",class_="bt",string=lambda v:v and "培训中心领导" in v);rows=[]
    for node in [heading.find_next_sibling("p"),heading.find_next_sibling("p").find_next_sibling("p")] if heading else []:
        m=re.match(r"\s*(主\s*任|副\s*主\s*任)[：:]\s*(.+)",node.get_text(" ",strip=True))
        if not m:continue
        duty=re.sub(r"\s+","",m.group(1))
        for raw_name in m.group(2).split("、"):
            name=re.sub(r"\s+","",raw_name)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"培训中心领导职务：名单"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
