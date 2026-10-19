from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"0247","page_type":"人物列表完整页","structure_group":"cjjg_leader_window_v2","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http","parser":"page_inline_cjjg_leader_window_v2","leader_region_selector":".leader-li a","name_selector":"b","duty_selector":"anchor text excluding b","detail_link_selector":".jgzzpage-lft2 dd a[href]","content_scope":{"start_anchor":"","end_anchor":"","include_selectors":[".leader-li",".jgzzpage-lft2"],"exclude_selectors":["script","style"]},"detail_strategy":{"required":False,"mode":"list_name_link_map","detail_collector_type":"static_http","detail_link_selector":".jgzzpage-lft2 dd a[href]","detail_parser":"","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":10},"risk_flag":"主卡链接均指领导栏目；真实独立人物链接按同页左侧姓名映射，若等于依据入口则留空","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_leader_window_name_map","locator":{"css":{"leader_region_selector":".leader-li a","name_selector":"b","detail_map_selector":".jgzzpage-lft2 dd a[href]"},"api":{"enabled":False,"reason":"当前原始HTML直接提供领导卡和人物链接映射"},"migration":{"source":"legacy_business_source_offline_dependency_and_entry_detail_removed","verified_status":"verified_current_raw_http","behavior_changed":True}}}

def compact(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+","",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser"); details={}
    for link in soup.select(page_rule["detail_link_selector"]):
        name=compact(link.get_text(" ",strip=True)); href=str(link.get("href") or "").strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",name) and href: details[name]=urljoin(final_url,href)
    rows=[]
    for item in soup.select(page_rule["leader_region_selector"]):
        name_node=item.select_one("b")
        if name_node is None: continue
        name=compact(name_node.get_text(" ",strip=True)); duty=compact(item.get_text(" ",strip=True)).removeprefix(name); candidate=details.get(name,"")
        detail_url="" if candidate.rstrip("/")==final_url.rstrip("/") else candidate
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",name) and duty: rows.append({"name":name,"duty":duty,"detail_url":detail_url,"source_text":duty,"method":page_rule["parser"],"note":"strategy=custom_parse_page；scope=leader_window；detail=name_map；order=card_dom"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
