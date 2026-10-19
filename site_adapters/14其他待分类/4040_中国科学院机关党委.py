from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4040","page_type":"领导正文页","structure_group":"cas_jgdw_title_name_lines","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cas_jgdw_title_name_lines_v1","leader_region_selector":"正文现任领导段","name_selector":"职务标签后姓名","duty_selector":"同段职务标签","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"中共中国科学院机关委员会主办","include_selectors":["正文p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"页面职务含“分管日常工作的”及“纪委书记”，均为当前职务的一部分。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验实时正文存在三行职务—姓名文本。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文现任领导段"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    text=BeautifulSoup(html,"html.parser").get_text(" ",strip=True);rows=[]
    for duty,names in re.findall(r"(分管日常工作的副书记|副书记、纪委书记|副书记)\s*[：:]\s*([^\s。；;]+)",text):
        for name in re.split(r"[、，,]",names):
            name=re.sub(r"[\s（(兼）)]+","",name)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"现任领导正文职务—姓名文本"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
