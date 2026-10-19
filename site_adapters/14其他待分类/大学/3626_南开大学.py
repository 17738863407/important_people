from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3626","domain":"www.nankai.edu.cn","page_type":"现任领导两列表格","structure_group":"nankai_leader_table_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"table_duty_name_detail","collector":"static_http","parser":"page_nankai_current_leaders_v1","leader_region_selector":"table.detail_tb","name_selector":"td:nth-of-type(2)","duty_selector":"td:nth-of-type(1)","detail_link_selector":"td:nth-of-type(2) a[href]","detail_strategy":{"required":False,"mode":"direct_person_link","candidate_links":[]},"risk_flag":"exact_current_leader_table","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_name(text:str)->str:
    """清理姓名中的排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip()

def clean_duty(node)->str:
    """将单元格内明确分隔的多项职务统一为全角分号。"""
    text=node.get_text("；",strip=True).replace("\u3000","；").replace("\xa0","；")
    text=re.sub(r"\s+","",text);text=re.sub(r"；+","；",text).strip("；：:")
    return text

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """从标题为现任领导的表格逐行提取。"""
    soup=BeautifulSoup(html,"html.parser");table=None
    for candidate in soup.select("table.detail_tb"):
        if "现任领导" in candidate.get_text(" ",strip=True):table=candidate;break
    if table is None:return []
    rows=[]
    for tr in table.select("tbody tr"):
        cells=tr.find_all("td",recursive=False)
        if len(cells)<2:continue
        link=cells[1].select_one("a[href]");name=clean_name(cells[1].get_text(" ",strip=True));duty=clean_duty(cells[0])
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
            detail=urljoin(final_url,str(link.get("href",""))) if link else ""
            rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":detail,"parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=table.detail_tb含现任领导；row=tbody tr；fields=td[0]+td[1]"})
    return rows

def main()->None:
    """运行当前页面级在线爬虫。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
