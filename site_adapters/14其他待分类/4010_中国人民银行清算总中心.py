from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4010","page_type":"清算中心现任领导卡片页","structure_group":"cncc_leader_items","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cncc_leader_items_v1","leader_region_selector":".con_conent","name_selector":".leader-item .name","duty_selector":".leader-item .justify","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"联系我们","include_selectors":[".con_conent"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"严格限于领导卡片容器。","confidence":"high","profile_reusable":False,"profile_judgement":"卡片内姓名、职务字段一一对应。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".con_conent","name_selector":".leader-item .name","duty_selector":".leader-item .justify"},"api":{"enabled":False,"reason":"HTML卡片完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    root=BeautifulSoup(html,"html.parser").select_one(".con_conent");rows=[]
    for card in root.select(".leader-item") if root else []:
        name=re.sub(r"\s+","",card.select_one(".name").get_text(" ",strip=True));duty=clean(card.select_one(".justify").get_text(" ",strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":".leader-item .name/.justify"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
