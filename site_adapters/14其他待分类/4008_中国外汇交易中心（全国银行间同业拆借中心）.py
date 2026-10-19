from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4008","page_type":"中心官网领导正文页","structure_group":"chinamoney_current_leaders_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_chinamoney_current_leaders_v1","leader_region_selector":"正文","name_selector":"现任领导班子职务：姓名","duty_selector":"职务标签","detail_link_selector":"","content_scope":{"start_anchor":"现任领导班子","end_anchor":"页脚","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅提取现任领导班子字段。","confidence":"high","profile_reusable":False,"profile_judgement":"页面以稳定职务：姓名列出当前领导。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    value=clean(BeautifulSoup(html,"html.parser").get_text(" ",strip=True));part=value[value.find("现任领导班子"):];rows=[]
    for duty,name in re.findall(r"(党委书记|总裁|纪委书记|副总裁)[：:]\s*([\u4e00-\u9fff]{2,4})",part):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"现任领导班子职务：姓名"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
