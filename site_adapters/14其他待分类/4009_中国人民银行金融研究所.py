from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4009","page_type":"研究所现任领导正文页","structure_group":"pbocri_current_leaders","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_pbocri_current_leaders_v1","leader_region_selector":"正文","name_selector":"姓名（职务）","duty_selector":"括号内职务","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"联系我们","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅限当前现任领导段。","confidence":"high","profile_reusable":False,"profile_judgement":"姓名及职务由稳定括号字段对应。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    value=clean(BeautifulSoup(html,"html.parser").get_text(" ",strip=True));start=value.rfind("现任领导");part=value[start:value.find("联系我们",start)];return [{"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"现任领导姓名（职务）"} for name,duty in re.findall(r"([\u4e00-\u9fff]{2,4})（([^）]+)）",part)]
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
