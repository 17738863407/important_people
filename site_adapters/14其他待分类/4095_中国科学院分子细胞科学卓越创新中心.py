from __future__ import annotations
import sys
from pathlib import Path

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4095","page_type":"领导卡片页","structure_group":"cemcs_strong_br_card","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_cemcs_strong_br_card","leader_region_selector":".mt20.row","risk_flag":"姓名与职务由换行分隔，忽略图片元素","confidence":"high","filter_policy":"strong_no_wordlist"}

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str,str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); rows=[]
    for card in soup.select(".mt20.row > div"):
        name=card.select_one("strong")
        lines=[x.strip() for x in card.select_one("p").get_text("\n",strip=True).splitlines() if x.strip()] if card.select_one("p") else []
        if name and len(lines)>=2:
            duty=lines[-1]; rows.append({"name":name.get_text(" ",strip=True),"duty":duty,"evidence":duty})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")

if __name__ == "__main__":main()
