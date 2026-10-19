from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id":"1467","page_type":"人物列表完整页","structure_group":"安徽省林业局机构领导列表",
 "reuse_scope":"single_page","load_mode":"动态DOM渲染","fetch_mode":"online","extract_mode":"list_direct",
 "collector":"browser_dom","parser":"page_anhui_forestry_public_list_v2","leader_region_selector":"#xxgk_lmcon",
 "name_selector":"a.title文本省林业局前部","duty_selector":"a.title文本省林业局起始后部","detail_link_selector":"a.title[href]",
 "risk_flag":"静态HTML无领导数据，必须解析浏览器渲染DOM","confidence":"high",
 "filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}


def clean_text(value: str) -> str:
    return re.sub(r"\s+"," ",str(value or "").replace("\u3000"," ").replace("\xa0"," ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup=BeautifulSoup(html,"html.parser"); rows=[]
    for link in soup.select("#xxgk_lmcon a.title[href]"):
        text=clean_text(str(link.get("title") or link.get_text(" ",strip=True)))
        match=re.fullmatch(r"(?P<name>[\u4e00-\u9fff\s·]{2,8})\s+(?P<duty>省林业局.+)",text)
        if not match: continue
        name=re.sub(r"\s+","",match.group("name")); duty=clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}",name): continue
        rows.append({"organization":page_rule["organization"],"url":page_rule["url"],"name":name,"duty":duty,
         "detail_url":urljoin(final_url,str(link.get("href") or "")),"evidence":duty,"confidence":"high",
         "parser":"page_anhui_forestry_public_list_v2","selector_summary":"strategy=custom_parse_page；item=#xxgk_lmcon a.title[href]；split=省林业局职务起点"})
    if not rows: raise RuntimeError("浏览器DOM未抽取到安徽省林业局领导")
    return rows


def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
