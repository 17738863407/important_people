from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup,Tag
PAGE_RULE={"rule_id":"3618","domain":"www.cufe.edu.cn","page_type":"现任领导职务分组","structure_group":"cufe_heading_following_list_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"heading_next_list_merge","collector":"static_http","parser":"page_cufe_current_leaders_v1","leader_region_selector":".xrld-left","name_selector":".xrld3 li a[href]","duty_selector":"h3","detail_link_selector":".xrld3 li a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"merge_multi_duties","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}
def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p/"crawler_core").is_dir():return p
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def clean(t:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(t or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按标题及其紧邻名单顺序提取并合并同人职务。"""
    s=BeautifulSoup(html,"html.parser");r=s.select_one(".xrld-left");store={}
    if r is None:return []
    for h in r.select("h3"):
        duty=clean(h.get_text(" ",strip=True));listing=h.find_next_sibling("div")
        if not isinstance(listing,Tag) or "xrld3" not in listing.get("class",[]):continue
        for a in listing.select("li a[href]"):
            name=clean(a.get_text(" ",strip=True))
            if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            row=store.setdefault(name,{"duties":[],"detail_url":urljoin(final_url,str(a.get("href","")))})
            if duty not in row["duties"]:row["duties"].append(duty)
    return [{"name":n,"duty":"；".join(d["duties"]),"evidence":"；".join(d["duties"]),"detail_url":str(d["detail_url"]),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.xrld-left；group=h3+div.xrld3；fields=li a；duties=merged"} for n,d in store.items()]
def main()->None:
    """运行当前页面级在线爬虫。"""
    p=resolve_project_dir()
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from crawler_core.runner import run_page_adapter
    c={};o=run_page_adapter(PAGE_RULE,globals(),runtime_context=c,update_fetch_memory=False);print(f"实际采集器：{c.get('actual_collector','')}");print(f"输出文件：{o}")
if __name__=="__main__":
    main()
