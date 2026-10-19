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

PAGE_RULE={"rule_id":"1027","page_type":"人物列表完整页","structure_group":"yellow_river_leader_table_v2","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http","parser":"page_inline_yellow_river_leader_table_v2","leader_region_selector":".art-cont tr","name_selector":"td:nth-of-type(1)","duty_selector":"td:nth-of-type(2)","detail_link_selector":"","content_scope":{"start_anchor":"","end_anchor":"","include_selectors":[".art-cont"],"exclude_selectors":["script","style"]},"detail_strategy":{"required":False,"mode":"none","detail_collector_type":"static_http","detail_link_selector":"","detail_parser":"","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":0},"risk_flag":"正文领导表格每行前两格为姓名职务强字段，页面无人物独立详情链接","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_leader_table","locator":{"css":{"leader_region_selector":".art-cont tr","name_selector":"td:nth-of-type(1)","duty_selector":"td:nth-of-type(2)"},"api":{"enabled":False,"reason":"当前静态HTML正文表格直接提供姓名职务"},"migration":{"source":"legacy_business_source_and_stale_link_metadata_removed","verified_status":"verified_current_raw_http","behavior_changed":True}}}

def compact(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+","",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    del final_url; soup=BeautifulSoup(html,"html.parser"); rows=[]
    for tr in soup.select(page_rule["leader_region_selector"]):
        cells=[compact(x.get_text(" ",strip=True)) for x in tr.select("td,th")]
        if len(cells)>=2 and re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",cells[0]) and cells[1]: rows.append({"name":cells[0],"duty":cells[1],"detail_url":"","source_text":cells[1],"method":page_rule["parser"],"note":"strategy=custom_parse_page；scope=leader_table；order=row_dom"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
