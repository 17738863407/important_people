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
    """从每个领导卡片的独立姓名文本和职务字段提取。"""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); source=final_url or str(page_rule.get("url","")); rows=[]
    for card in soup.select(".ldzc-list"):
        heading=card.select_one(".jbxx h1"); duty_node=card.select_one(".jbxx > span")
        direct="".join(str(x) for x in heading.find_all(string=True,recursive=False)) if heading else ""
        name=clean_text(direct).replace(" ",""); duty=clean_text(duty_node.get_text(" ",strip=True)) if duty_node else ""
        link=heading.select_one("a.ldjj[href]") if heading else None
        if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}",name):
            rows.append({"name":name,"duty":"","evidence":duty,"detail_url":urljoin(source,str(link.get("href") or "")) if link else "","confidence":"high","parser":"page_inline_jingdezhen_government_cards_v1"})
    return rows

PAGE_RULE={"rule_id":"3841","page_type":"领导信息卡片页","load_mode":"静态HTML直出","fetch_mode":"raw_http","_fetch_mode_override":True,"extract_mode":"list_direct","parser":"page_inline_jingdezhen_government_cards_v1","leader_region_selector":".ldzc-list","name_selector":".jbxx h1","duty_selector":".jbxx > span","detail_link_selector":"a.ldjj[href]","locator_strategy":"custom_parse_page","risk_flag":"","confidence":"high"}

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals(),update_fetch_memory=False)
    print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
