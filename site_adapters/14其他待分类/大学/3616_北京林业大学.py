from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
PAGE_RULE={"rule_id":"3616","domain":"www.bjfu.edu.cn","page_type":"现任领导职务分组","structure_group":"bjfu_wraplist9_leaders_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"grouped_titles_names_merge","collector":"static_http","parser":"page_bjfu_current_leaders_v1","leader_region_selector":".wrap-wraplist9","name_selector":".list9 .listTitle","duty_selector":"h2.commonTitle","detail_link_selector":".list9 a[href]","detail_strategy":{"required":False,"mode":"optional_person_link","candidate_links":[]},"risk_flag":"merge_duties_links_optional","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}
def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p/"crawler_core").is_dir():return p
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def clean(t:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(t or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按职务分组顺序提取，合并同人职务并保留首个真实人物链接。"""
    s=BeautifulSoup(html,"html.parser");r=s.select_one(".wrap-wraplist9");store={}
    if r is None:return []
    for g in r.select(".wraplist9"):
        dn=g.select_one("h2.commonTitle");duty=clean(dn.get_text(" ",strip=True) if dn else "")
        for item in g.select("ul.list9>li"):
            n=item.select_one(".listTitle");name=clean(n.get_text(" ",strip=True) if n else "");a=item.select_one("a[href]");detail=urljoin(final_url,str(a.get("href",""))) if a else ""
            if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            row=store.setdefault(name,{"duties":[],"detail_url":detail})
            if duty not in row["duties"]:row["duties"].append(duty)
            if not row["detail_url"] and detail:row["detail_url"]=detail
    return [{"name":n,"duty":"；".join(d["duties"]),"evidence":"；".join(d["duties"]),"detail_url":str(d["detail_url"]),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.wrap-wraplist9；group=.wraplist9；fields=h2.commonTitle+.listTitle；duties=merged"} for n,d in store.items()]
def main()->None:
    """运行当前页面级在线爬虫。"""
    p=resolve_project_dir()
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from crawler_core.runner import run_page_adapter
    c={};o=run_page_adapter(PAGE_RULE,globals(),runtime_context=c,update_fetch_memory=False);print(f"实际采集器：{c.get('actual_collector','')}");print(f"输出文件：{o}")
if __name__=="__main__":
    main()
