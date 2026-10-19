from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4062","page_type":"研究所领导正文页","structure_group":"ivpp_title_bio_pair_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ivpp_title_bio_pair_v1","leader_region_selector":"正文p的职务标题—姓名首句相邻对","name_selector":"职务标题后首个p首名","duty_selector":"职务标题p","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"版权所有","include_selectors":["p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅将独立职务标题与紧邻履历首句配对。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验4组职务标题—姓名履历首句。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文相邻p"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");ps=[p for p in soup.select("div.trs_editor_view > p") if p.get_text(" ",strip=True)];rows=[]
    for i,p in enumerate(ps[:-1]):
        duty=p.get_text(" ",strip=True)
        if not re.fullmatch(r"(?:所长|副所长|纪委书记|党委书记、副所长)",duty): continue
        text=ps[i+1].get_text(" ",strip=True);m=re.match(r"([\u4e00-\u9fff]{2,4})\s*\(",text)
        if m: rows.append({"name":m.group(1),"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"正文相邻职务标题p与履历首句p"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
