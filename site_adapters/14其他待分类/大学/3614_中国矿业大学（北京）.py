from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
PAGE_RULE={"rule_id":"3614","domain":"www.cumtb.edu.cn","page_type":"现任领导双栏表格","structure_group":"cumtb_leader_table_pairs_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"paired_duty_name_cells_merge","collector":"static_http","parser":"page_cumtb_current_leaders_v1","leader_region_selector":".v_news_content table","name_selector":"td .ry, td a[href]","duty_selector":"td .zc","detail_link_selector":"td .ry a[href], td>a[href]","detail_strategy":{"required":False,"mode":"validated_person_link","candidate_links":[]},"risk_flag":"paired_cells_and_rowspan_merge","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}
def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p/"crawler_core").is_dir():return p
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def clean(t:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(t or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按表格行及左右栏顺序提取，合并同人多项职务。"""
    s=BeautifulSoup(html,"html.parser");table=s.select_one(".v_news_content table") or s.find("table")
    if table is None:return []
    store:dict[str,dict[str,object]]={}
    for tr in table.select("tr"):
        cells=tr.find_all("td",recursive=False)
        for i in range(0,len(cells)-1,2):
            dn=cells[i].select_one(".zc");duty=clean(dn.get_text(" ",strip=True) if dn else "")
            if not duty:continue
            nc=cells[i+1];nodes=nc.select("span.ry") or nc.select("a[href]")
            for node in nodes:
                name=clean(node.get_text(" ",strip=True));link=node if node.name=="a" else node.select_one("a[href]");detail=urljoin(final_url,str(link.get("href",""))) if link else ""
                if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
                row=store.setdefault(name,{"duties":[],"detail_url":detail})
                if duty not in row["duties"]:row["duties"].append(duty)
                if not row["detail_url"] and detail:row["detail_url"]=detail
    return [{"name":n,"duty":"；".join(d["duties"]),"evidence":"；".join(d["duties"]),"detail_url":str(d["detail_url"]),"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=leader table；row=tr；fields=paired .zc+next td .ry；duties=merged"} for n,d in store.items()]
def main()->None:
    """运行当前页面级在线爬虫。"""
    p=resolve_project_dir()
    if str(p) not in sys.path:sys.path.insert(0,str(p))
    from crawler_core.runner import run_page_adapter
    c={};o=run_page_adapter(PAGE_RULE,globals(),runtime_context=c,update_fetch_memory=False);print(f"实际采集器：{c.get('actual_collector','')}");print(f"输出文件：{o}")
if __name__=="__main__":
    main()
