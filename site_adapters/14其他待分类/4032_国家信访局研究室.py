from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4032","page_type":"机构设置职责页","structure_group":"gjxfj_principal_sibling","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_gjxfj_principal_sibling_v1","leader_region_selector":"机构正文中“主要负责人”相邻段","name_selector":"主要负责人标签后的p","duty_selector":"固定标签“主要负责人”","detail_link_selector":"","content_scope":{"start_anchor":"研究室","end_anchor":"内设机构","include_selectors":[".article, .content, div"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"页面仅公开主要负责人姓名，不把机构职责误作个人职务。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验“主要负责人”强标签的紧邻段为唯一姓名。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"主要负责人标签父div"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");label=soup.find(string=lambda v:v and "主要负责人" in v);holder=label.find_parent("p").parent if label and label.find_parent("p") else None
    if not holder:return []
    ps=holder.find_all("p",recursive=False);index=next((i for i,p in enumerate(ps) if "主要负责人" in p.get_text(" ",strip=True)),-1)
    name=re.sub(r"\s+","",ps[index+1].get_text(" ",strip=True)) if 0<=index<len(ps)-1 else ""
    return [{"name":name,"duty":"主要负责人","detail_url":"","evidence":"主要负责人","parser":str(page_rule["parser"]),"selector_summary":"“主要负责人”标签后的直接p"}] if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) else []
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
