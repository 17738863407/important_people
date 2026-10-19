from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urljoin
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4099","page_type":"领导卡片页","structure_group":"sari_leader_h2_h3_card","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_sari_leader_h2_h3_card","leader_region_selector":".leader-box","risk_flag":"详情链接位于当前卡片的父级链接","confidence":"high","filter_policy":"strong_no_wordlist"}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    from bs4 import BeautifulSoup
    s=BeautifulSoup(html,'html.parser');rows=[]
    for c in s.select('.leader-box'):
        n,d=c.select_one('h2'),c.select_one('h3');a=c.find_parent('a',href=True)
        if n and d:rows.append({'name':n.get_text(' ',strip=True),'duty':d.get_text(' ',strip=True),'evidence':d.get_text(' ',strip=True),'detail_url':urljoin(final_url,a['href']) if a else ''})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=='__main__':main()
