from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4065","page_type":"研究所领导链接列表页","structure_group":"ioz_bai13_label_name_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ioz_bai13_label_name_v1","leader_region_selector":"a.bai13[href$='.html']","name_selector":"a直系文本冒号后","duty_selector":"a直系文本冒号前","detail_link_selector":"a.bai13[href$='.html']","content_scope":{"start_anchor":"现任领导","end_anchor":"关于我们","include_selectors":["a.bai13[href$='.html']"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"card_link"},"risk_flag":"姓名和职务处于同一动态文本节点。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验5条冒号分隔领导链接。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"a.bai13[href$='.html']"},"api":{"enabled":False,"reason":"HTML链接列表完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for a in soup.select("a.bai13[href$='.html']"):
        m=re.match(r"\s*(.+?)[：:]\s*([\u4e00-\u9fff]{2,4})\s*$",a.get_text(" ",strip=True))
        if m:rows.append({"name":m.group(2),"duty":re.sub(r"\s+","",m.group(1)),"detail_url":a["href"],"evidence":re.sub(r"\s+","",m.group(1)),"parser":str(page_rule["parser"]),"selector_summary":"现任领导bai13冒号文本链接"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
