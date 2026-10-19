from __future__ import annotations
import re
import sys
from pathlib import Path

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4169","page_type":"局领导介绍页","structure_group":"cass_retired_cadre_office_leaders","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_cass_retired_cadre_v1","leader_region_selector":"body","name_selector":"","duty_selector":"","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none"},"risk_flag":"局领导与办公地址相邻，按职务字段边界提取。","confidence":"high","filter_policy":"strong_no_wordlist"}

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup
    lines=list(BeautifulSoup(html,"html.parser").stripped_strings)
    start=next((i for i,x in enumerate(lines) if x=="离退休干部局局领导"),None)
    if start is None: return []
    rows=[]
    for i,line in enumerate(lines[start+1:],start+1):
        if "办公室" in line: continue
        compact=re.sub(r"\s+","",line)
        match=re.match(r"(局长|副局长)[：:](.*)",compact)
        if match and not match.group(2) and i+1<len(lines):
            match=re.match(r"(局长|副局长)[：:](.*)",compact+re.sub(r"\s+","",lines[i+1]))
        if match:
            name=re.match(r"[\u4e00-\u9fff·]{2,4}",match.group(2))
            if name: rows.append({"name":name.group(),"duty":match.group(1),"detail_url":""})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE,globals())}")

if __name__ == "__main__":
    main()
