from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4012","page_type":"培训学院领导双列正文页","structure_group":"pbcti_leader_pairs","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_pbcti_leader_pairs_v1","leader_region_selector":".single-article","name_selector":"直接子div奇数项","duty_selector":"直接子div偶数项","detail_link_selector":"","content_scope":{"start_anchor":"学院领导","end_anchor":"版权所有","include_selectors":[".single-article"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"姓名、职务按同一行相邻div对应。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前文章为稳定的姓名—职务相邻双列结构。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".single-article"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    root=BeautifulSoup(html,"html.parser").select_one(".single-article > div");nodes=root.find_all("div",recursive=False) if root else [];rows=[]
    for name_node,duty_node in zip(nodes[0::2],nodes[1::2]):
        name=re.sub(r"\s+","",name_node.get_text(" ",strip=True));duty=clean(duty_node.get_text(" ",strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":".single-article相邻姓名/职务div"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
