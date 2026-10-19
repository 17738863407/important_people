from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE={"rule_id":"1738","page_type":"职务分组名单页","structure_group":"安徽省民宗委领导目录",
"reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct",
"collector":"static_http","parser":"page_inline_anhui_mwzjj_title_links_v2","leader_region_selector":"a.title[href*='/public/6991/']",
"name_selector":"链接文本冒号后","duty_selector":"链接文本冒号前","detail_link_selector":"a.title[href*='/public/6991/']",
"risk_flag":"requests丢失catId并进入普通公开列表","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}


def clean_text(v:str)->str:return re.sub(r"\s+"," ",str(v or "").replace("\u3000"," ").replace("\xa0"," ")).strip()


def clean_standalone_concurrent_marker(v:str)->str:
    duty=re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])","",clean_text(v))
    return re.sub(r"[，,、；;：:]\s*$","",duty).strip()


def parse_page(html:str,final_url:str,page_rule:dict)->list[dict]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for link in soup.select("a.title[href*='/public/6991/']"):
        parts=clean_text(link.get_text(" ",strip=True)).split("：",1)
        if len(parts)!=2:continue
        duty,name=clean_standalone_concurrent_marker(parts[0]),re.sub(r"\s+","",parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}",name) or not duty:continue
        rows.append({"organization":page_rule["organization"],"url":page_rule["url"],"name":name,"duty":duty,
        "detail_url":urljoin(final_url,str(link.get("href") or "")),"evidence":duty,"confidence":"high",
        "parser":"page_inline_anhui_mwzjj_title_links_v2","selector_summary":"strategy=custom_parse_page；item=a.title[href*=/public/6991/]；split=中文冒号"})
    if not rows:raise RuntimeError("安徽省民宗委领导目录未抽取到人物")
    return rows


def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")


if __name__=="__main__":main()
