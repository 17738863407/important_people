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

PAGE_RULE={"rule_id":"4094","page_type":"领导卡片页","structure_group":"shao_leader_link_list","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_shao_leader_link_list","leader_region_selector":"ul","risk_flag":"姓名职务同在人物链接，按职务后姓名切分","confidence":"high","filter_policy":"strong_no_wordlist"}

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str,str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); rows=[]
    for link in soup.select("ul li > p > a[href]"):
        text=re.sub(r"\s+|：","",link.get_text(" ",strip=True)); split=next(((text[:-n],text[-n:]) for n in (2,3,4) if re.search(r"(?:台长|书记|主任|院长)$",text[:-n])),None)
        if split: rows.append({"name":split[1],"duty":split[0],"evidence":split[0],"detail_url":urljoin(final_url,link["href"])})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")

if __name__ == "__main__": main()
