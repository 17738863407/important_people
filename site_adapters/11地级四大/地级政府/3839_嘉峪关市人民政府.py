from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """兼容市长首卡和其他职务分组卡片。"""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); region=soup.select_one(".ld-ldxq")
    if region is None: return []
    source=final_url or str(page_rule.get("url","")); rows=[]
    for group in region.find_all("div",recursive=False):
        duty_node=group.select_one(":scope > .ld-dzw, :scope > .ld-zw")
        duty=clean_text(duty_node.get_text(" ",strip=True)) if duty_node else ""
        for link in group.select("a[href]"):
            name_node=link.select_one(".ld-xx-name")
            name=clean_text(name_node.get_text(" ",strip=True)).replace(" ","") if name_node else clean_text(str(link.get("title") or "")).replace(" ","")
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}",name):
                rows.append({"name":name,"duty":"","evidence":duty,"detail_url":urljoin(source,str(link.get("href") or "")),"confidence":"high","parser":"page_inline_jiayuguan_government_groups_v1"})
    return rows

PAGE_RULE={"rule_id":"3839","page_type":"职务分组卡片页","load_mode":"静态HTML直出","fetch_mode":"raw_http","_fetch_mode_override":True,"extract_mode":"list_direct","parser":"page_inline_jiayuguan_government_groups_v1","leader_region_selector":".ld-ldxq","name_selector":".ld-xx-name","duty_selector":".ld-dzw, .ld-zw","detail_link_selector":"a[href]","locator_strategy":"custom_parse_page","risk_flag":"","confidence":"high"}

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals(),update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
