from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4053","page_type":"研究所领导卡片页","structure_group":"ioa_menu_mod02_leaders","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ioa_menu_mod02_leaders_v1","leader_region_selector":".menu-mod-02 .box-s","name_selector":"a.name-s","duty_selector":".job-s","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"机构设置","include_selectors":[".menu-mod-02"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"人物链接为javascript占位，不写详情页。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前5张领导卡片中的姓名、职务字段。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".menu-mod-02 .box-s"},"api":{"enabled":False,"reason":"HTML直接呈现卡片"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    rows=[]
    for card in BeautifulSoup(html,"html.parser").select('.menu-mod-02 .box-s'):
        name=re.sub(r"\s+","",card.select_one('.name-s').get_text(' ',strip=True));duty=re.sub(r"\s+","",card.select_one('.job-s').get_text(' ',strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule['parser']),"selector_summary":".menu-mod-02 .box-s"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
