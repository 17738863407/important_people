from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE={"rule_id":"1691","page_type":"人物列表完整页","structure_group":"药监局领导姓名简介块",
"reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"list_direct",
"collector":"static_http","parser":"anhui_mpa_name_profile_v2","leader_region_selector":"#wenzhang",
"name_selector":"姓名标签后文本","duty_selector":"同一简介块完整现任句","detail_link_selector":"",
"risk_flag":"正文含分工，仅提取各简介块完整现任句","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}


def clean_text(value:str)->str:
    return re.sub(r"\s+"," ",str(value or "").replace("\u3000"," ").replace("\xa0"," ")).strip()


def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
    soup=BeautifulSoup(html,"html.parser"); content=soup.select_one("#wenzhang")
    if content is None: raise RuntimeError("未定位到安徽省药监局领导正文")
    text=clean_text(content.get_text(" ",strip=True)); rows=[]
    pattern=re.compile(r"姓\s*名[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,4})\s+简\s*介[:：]\s*(?P<body>.*?)(?=姓\s*名[:：]|文件下载|$)")
    for match in pattern.finditer(text):
        duty_match=re.search(r"现任[^。]*。",match.group("body"))
        if not duty_match: continue
        evidence=clean_text(duty_match.group(0)); name=match.group("name")
        evidence=re.sub(r"^现任\s*", "", evidence)
        evidence=re.sub(r"。\s*$", "", evidence)
        rows.append({"organization":page_rule["organization"],"url":page_rule["url"],"name":name,"duty":evidence,
        "detail_url":"","evidence":evidence,"confidence":"high","parser":"anhui_mpa_name_profile_v2",
        "selector_summary":"strategy=custom_parse_page；scope=#wenzhang；block=姓名/简介；duty=同块完整现任句"})
    if not rows: raise RuntimeError("安徽省药监局领导简介未抽取到人物")
    return rows


def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")


if __name__=="__main__": main()
