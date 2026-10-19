from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urljoin
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4098","page_type":"领导卡片页","structure_group":"simm_xrld_item_content","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_simm_xrld_item_content","leader_region_selector":".xrld-item-content","risk_flag":"卡片同时展示职称，依据说明仅取首个职务标签","confidence":"high","filter_policy":"strong_no_wordlist"}
def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    from bs4 import BeautifulSoup
    s=BeautifulSoup(html,"html.parser");rows=[]
    for c in s.select('.xrld-item-content'):
        a=c.select_one('header a[href]');d=c.select_one('.xrld-item-content-title')
        if a and d:
            href=str(a.get('href','')).strip()
            rows.append({'name':''.join(a.get_text(' ',strip=True).split()),'duty':d.get_text(' ',strip=True),'evidence':d.get_text(' ',strip=True),'detail_url':urljoin(final_url,href) if href and href.lower()!='false' else ''})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=='__main__':main()
