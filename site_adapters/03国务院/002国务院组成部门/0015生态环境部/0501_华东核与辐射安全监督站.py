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

PAGE_RULE={"rule_id":"0501","page_type":"人物列表完整页","structure_group":"ecro_leader_categories_v2","reuse_scope":"single_page","load_mode":"动态跳转后静态分类","fetch_mode":"online","force_browser":True,"extract_mode":"list_direct","collector":"browser_entry_plus_static_categories","parser":"page_inline_ecro_leader_categories_v2","leader_region_selector":".main_left_m a[href]","name_selector":".main_right_m li a[title][href]","duty_selector":".main_right_t .title","detail_link_selector":".main_right_m li a[title][href]","content_scope":{"start_anchor":"主要领导","end_anchor":"","include_selectors":[".main_left_m",".main_right_m"],"exclude_selectors":["footer","script","style"]},"detail_strategy":{"required":False,"mode":"category_list_link_only","detail_collector_type":"static_http","detail_link_selector":".main_right_m li a[title][href]","detail_parser":"","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":20},"risk_flag":"权威入口为即时跳转壳页；浏览器落地后按左侧职务分类动态发现四个静态名单页","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_category_lists","locator":{"css":{"category_selector":".main_left_m a[href]","category_title":".main_right_t .title","person_selector":".main_right_m li a[title][href]"},"api":{"enabled":False,"reason":"落地页、分类页与人物链接均可在线复现"},"migration":{"source":"legacy_business_source_offline_dependency_and_detail_body_evidence_removed","verified_status":"verified_current_browser_entry_and_raw_categories","behavior_changed":True}}}

def clean(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+"," ",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    from crawler_core.fetcher import fetch_by_raw_requests
    soup=BeautifulSoup(html,"html.parser"); category_urls=[]
    for link in soup.select(page_rule["leader_region_selector"]):
        url=urljoin(final_url,str(link.get("href") or ""))
        if url and url not in category_urls: category_urls.append(url)
    rows=[]; seen=set()
    for category_url in category_urls:
        try: result=fetch_by_raw_requests(category_url,timeout=45)
        except Exception: continue
        category=BeautifulSoup(result.html,"html.parser"); title=category.select_one(page_rule["duty_selector"]); duty=clean(title.get_text(" ",strip=True)) if title else ""
        if not duty: continue
        for link in category.select(page_rule["name_selector"]):
            name=clean(str(link.get("title") or link.get_text(" ",strip=True))).replace(" ",""); href=str(link.get("href") or "").strip(); detail_url=urljoin(result.final_url,href); key=(name,duty,detail_url)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",name) and key not in seen:
                seen.add(key); rows.append({"name":name,"duty":duty,"detail_url":detail_url,"source_text":duty,"method":page_rule["parser"],"note":"strategy=custom_category_lists；scope=current_category；order=category_then_item"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
