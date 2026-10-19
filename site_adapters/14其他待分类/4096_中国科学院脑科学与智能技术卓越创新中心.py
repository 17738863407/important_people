from __future__ import annotations
import sys
from pathlib import Path

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4096","page_type":"领导表格页","structure_group":"cebsit_strong_pair_table","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_cebsit_strong_pair_table","leader_region_selector":"table","risk_flag":"职务含研究员头衔，依据说明仅保留职务部分","confidence":"high","filter_policy":"strong_no_wordlist"}

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str,str]]:
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,"html.parser"); rows=[]
    for row in soup.select("table tr"):
        values=[n.get_text(" ",strip=True) for n in row.select("td strong")]
        for i in range(0,len(values)-1,2):
            name,duty=values[i],values[i+1].split("、高级研究员",1)[0]
            if name and any(k in duty for k in ("主任","书记","院长","所长")):rows.append({"name":name,"duty":duty,"evidence":duty})
    return rows

def main() -> None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")

if __name__ == "__main__":main()
