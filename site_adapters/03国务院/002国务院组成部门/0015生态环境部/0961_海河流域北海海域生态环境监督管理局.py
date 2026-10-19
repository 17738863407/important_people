from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"0961","page_type":"人物列表完整页","structure_group":"hhbhjg_leader_list_v2","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http","parser":"page_inline_hhbhjg_leader_list_v2","leader_region_selector":".hhej_ldr_list .hhej_ldr_name","name_selector":"span","duty_selector":"em","detail_link_selector":"","content_scope":{"start_anchor":"","end_anchor":"","include_selectors":[".hhej_ldr_list"],"exclude_selectors":["script","style"]},"detail_strategy":{"required":False,"mode":"none","detail_collector_type":"static_http","detail_link_selector":"","detail_parser":"","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":0},"risk_flag":"当前原始HTML直接含领导列表；仅解析hhej_ldr_name的span/em强字段","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_leader_list","locator":{"css":{"leader_region_selector":".hhej_ldr_list .hhej_ldr_name","name_selector":"span","duty_selector":"em"},"api":{"enabled":False,"reason":"当前原始HTML直接提供姓名职务"},"migration":{"source":"legacy_dynamic_offline_dependency_and_brittle_absolute_selector_removed","verified_status":"verified_current_raw_http","behavior_changed":True}}}

def compact(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+","",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    del final_url; soup=BeautifulSoup(html,"html.parser"); rows=[]
    for item in soup.select(page_rule["leader_region_selector"]):
        name_node=item.select_one(page_rule["name_selector"]); duty_node=item.select_one(page_rule["duty_selector"])
        if name_node is None or duty_node is None: continue
        name=compact(name_node.get_text(" ",strip=True)); duty=compact(duty_node.get_text(" ",strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",name) and duty: rows.append({"name":name,"duty":duty,"detail_url":"","source_text":duty,"method":page_rule["parser"],"note":"strategy=custom_parse_page；scope=hhej_leader_list；order=item_dom"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
