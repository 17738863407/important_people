from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3646","domain":"www.njau.edu.cn","page_type":"现任领导简介文章列表","structure_group":"njau_leader_article_list_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"article_title_duty_name","collector":"static_http","parser":"page_njau_current_leaders_v1","leader_region_selector":"ul.news_list","name_selector":"li.news .news_title a[href]","duty_selector":"li.news .news_title a[href]","detail_link_selector":"li.news .news_title a[href]","detail_strategy":{"required":True,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"use_article_title_not_inconsistent_excerpt","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip()

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """以列表文章标题“职务：姓名”为权威字段，不采用可能不一致的摘要。"""
    soup=BeautifulSoup(html,"html.parser");regions=[]
    for ul in soup.select("ul.news_list"):
        links=ul.select("li.news .news_title a[href]");count=sum(1 for link in links if re.fullmatch(r".+?[:：][\u4e00-\u9fff·]{2,5}",clean(link.get_text(" ",strip=True))))
        if count:regions.append((count,ul))
    if not regions:return []
    region=max(regions,key=lambda item:item[0])[1];rows=[]
    for link in region.select("li.news .news_title a[href]"):
        match=re.fullmatch(r"(.+?)[:：]([\u4e00-\u9fff·]{2,5})",clean(link.get_text(" ",strip=True)))
        if match:
            duty,name=match.group(1),match.group(2);href=str(link.get("href",""));detail=urljoin(final_url,href) if href and not href.startswith(("#","javascript:","mailto:")) else ""
            if detail.rstrip("/")==final_url.rstrip("/"):detail=""
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":detail,"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=有效职务冒号姓名最多的ul.news_list；field=.news_title a"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
