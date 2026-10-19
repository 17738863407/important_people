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

PAGE_RULE={"rule_id":"1026","page_type":"人物列表完整页","structure_group":"huaihe_leader_detail_nav_v2","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http_detail_nav","parser":"page_inline_huaihe_leader_detail_nav_v2","leader_region_selector":".jgjs_left_nav a[href]","name_selector":"","duty_selector":"","detail_link_selector":".jgjs_left_nav a[href]","content_scope":{"start_anchor":"局领导","end_anchor":"内设机构及直属单位","include_selectors":[".jgjs_left_nav",".art-list-lxwm4"],"exclude_selectors":["script","style"]},"detail_strategy":{"required":True,"mode":"custom_nav_to_detail","detail_collector_type":"static_http","detail_link_selector":".jgjs_left_nav a[href]","detail_parser":"detail_heading_before_resume","detail_name_selector":"","detail_duty_selector":".art-list-lxwm4","detail_content_selector":".art-list-lxwm4","max_detail_links":20},"risk_flag":"左侧导航混含非人物栏目；仅接受详情正文开头严格匹配导航姓名且其后存在个人简历边界的页面","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"page_inline_validated_nav_details","locator":{"css":{"nav_selector":".jgjs_left_nav a[href]","detail_scope":".art-list-lxwm4","boundary":"name then duty then 个人简历"},"api":{"enabled":False,"reason":"当前静态HTML导航和详情页可复现"},"migration":{"source":"legacy_local_file_dependency_and_unvalidated_nav_removed","verified_status":"verified_current_raw_http_details","behavior_changed":True}}}

def compact(value:str)->str: return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+","",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    from crawler_core.fetcher import fetch_by_raw_requests
    soup=BeautifulSoup(html,"html.parser"); rows=[]; seen=set()
    for link in soup.select(page_rule["leader_region_selector"]):
        name=compact(link.get_text(" ",strip=True)); href=str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}",name) or not href: continue
        detail_url=urljoin(final_url,href)
        try: result=fetch_by_raw_requests(detail_url,timeout=45)
        except Exception: continue
        box=BeautifulSoup(result.html,"html.parser").select_one(".art-list-lxwm4")
        text=compact(box.get_text(" ",strip=True)) if box else ""; match=re.match(re.escape(name)+r"(?P<duty>.+?)个人简历",text)
        if match is None: continue
        duty=match.group("duty"); key=(name,duty)
        if key in seen: continue
        seen.add(key); exported_detail="" if detail_url.rstrip("/")==final_url.rstrip("/") else detail_url
        rows.append({"name":name,"duty":duty,"detail_url":exported_detail,"source_text":duty,"method":page_rule["parser"],"note":"strategy=custom_nav_to_detail；scope=detail_heading；order=nav_dom"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
