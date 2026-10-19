from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3621","domain":"www.chntheatre.edu.cn","page_type":"职务标题多人名单","structure_group":"chntheatre_current_leaders_2026","reuse_scope":"single_page","load_mode":"动态DOM渲染","force_browser":True,"fetch_mode":"online","extract_mode":"grouped_title_names","collector":"playwright","parser":"page_chntheatre_current_leaders_v1","leader_region_selector":".survey3","name_selector":".name a","duty_selector":".job","detail_link_selector":".name a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"http_403_requires_browser;exclude_previous_leaders","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    """清理姓名或职务中的排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """限定现任领导区，按职务组首次出现顺序合并同一人物的现职。"""
    soup=BeautifulSoup(html,"html.parser");region=soup.select_one(".survey3");ordered=[];by_name={}
    if region is None:return []
    for item in region.select(".list .li"):
        job=item.select_one(".job");duty=clean(job.get_text(" ",strip=True) if job else "")
        if not duty:continue
        for link in item.select(".name a[href]"):
            name=clean(link.get_text(" ",strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name):continue
            if name not in by_name:
                by_name[name]={"name":name,"duties":[],"detail_url":urljoin(final_url,str(link.get("href","")))};ordered.append(name)
            if duty not in by_name[name]["duties"]:by_name[name]["duties"].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]["duties"]),"evidence":"；".join(by_name[name]["duties"]),"detail_url":by_name[name]["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=.survey3；group=.list .li；fields=.job+.name a"} for name in ordered]

def main()->None:
    """运行当前页面级在线爬虫。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
