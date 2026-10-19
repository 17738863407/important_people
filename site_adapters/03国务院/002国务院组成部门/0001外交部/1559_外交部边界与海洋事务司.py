from __future__ import annotations
import re, sys
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup

PAGE_RULE: dict[str, Any] = {"rule_id":"1559","page_type":"人物列表完整页","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"页面内置parse_page","leader_region_selector":".main dl.info.clearfix .desc","parser_id":"custom_mfa_department_duty_names_v2","structure_group":"部门信息_职务冒号多人名单","confidence":"high","risk_notes":"允许姓名后网页性别注记，姓名字段仅保留姓名；排除职责、电话、新闻和导航。"}
def _clean(v:str)->str: return re.sub(r"\s+"," ",v.replace("\xa0"," ").replace("\u3000"," ")).strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,Any])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser"); scopes=soup.select(page_rule["leader_region_selector"])
    if len(scopes)!=1: raise RuntimeError(f"部门领导信息容器数量异常：{len(scopes)}")
    rows=[]
    for node in scopes[0].select(":scope > .si_name, :scope > p"):
        m=re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<names>.+)",_clean(node.get_text(" ",strip=True)))
        if m is None: continue
        duty=re.sub(r"\s+","",m.group("duty")); parsed=[]
        for token in re.split(r"[、，,；;]+",m.group("names")):
            compact=re.sub(r"\s+","",token); nm=re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,6})(?:[（(][男女][）)])?",compact)
            if nm is None: parsed=[]; break
            parsed.append(nm.group("name"))
        rows.extend({"name":n,"duty":duty,"detail_url":""} for n in parsed)
    if not rows: raise RuntimeError("部门领导信息未解析到有效人物")
    return rows
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__": main()
