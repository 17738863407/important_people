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

PAGE_RULE={"rule_id":"1980","page_type":"人物列表完整页","structure_group":"npc_agriculture_committee_iframe_v2","reuse_scope":"single_page","load_mode":"iframe嵌入","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http_iframe","parser":"page_inline_npc_agriculture_committee_iframe_v2","leader_region_selector":"iframe[src*='nyyncwyh2023012']","name_selector":"","duty_selector":"","detail_link_selector":"","content_scope":{"start_anchor":"主任委员","end_anchor":"民族委员会","include_selectors":["iframe[src*='nyyncwyh2023012']"],"exclude_selectors":["script","style"]},"detail_strategy":{"required":False,"mode":"none","detail_collector_type":"static_http","detail_link_selector":"","detail_parser":"","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":0},"risk_flag":"入口含多个iframe；仅动态发现nyyncwyh2023012名单框架并按三个职务标题分段","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_target_iframe_sections","locator":{"css":{"frame_selector":"iframe[src*='nyyncwyh2023012']"},"api":{"enabled":False,"reason":"目标iframe静态HTML直接提供完整分组名单"},"migration":{"source":"legacy_business_source_and_implicit_browser_flattening_removed","verified_status":"verified_current_entry_and_frame_raw_http","behavior_changed":True}}}

def normalize_space(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+"," ",value or "").strip()
def clean_name(value:str)->str: return re.sub(r"\s+","",re.sub(r"（[^）]*）|\([^)]*\)","",normalize_space(value))).strip("：:，,。.；;")
def split_names(value:str)->list[str]:
    tokens=[clean_name(x) for x in normalize_space(value).split(" ") if clean_name(x)]; names=[]; i=0
    while i<len(tokens):
        token=tokens[i]
        if len(token)==1 and i+1<len(tokens) and len(tokens[i+1])==1: token+=tokens[i+1]; i+=2
        else: i+=1
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",token): names.append(token)
    return names

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    from crawler_core.fetcher import fetch_by_raw_requests
    frame=BeautifulSoup(html,"html.parser").select_one(page_rule["leader_region_selector"])
    if frame is None or not frame.get("src"): return []
    result=fetch_by_raw_requests(urljoin(final_url,str(frame.get("src"))),timeout=45); text=normalize_space(BeautifulSoup(result.html,"html.parser").get_text(" ",strip=True)); rows=[]
    groups=(("主任委员",re.search(r"主任委员\s+(.*?)\s+副主任委员",text)),("副主任委员",re.search(r"副主任委员\s+(.*?)\s+委员\s+（按姓名笔划为序排列）",text)))
    for duty,match in groups:
        if match:
            for name in split_names(match.group(1)): rows.append({"name":name,"duty":duty,"detail_url":"","source_text":duty,"method":page_rule["parser"],"note":"strategy=custom_parse_page；scope=target_iframe_section；order=section_then_name"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
