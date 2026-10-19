from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup,NavigableString
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4072","page_type":"研究所领导正文列表页","structure_group":"ime_b_label_sibling_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ime_b_label_sibling_v1","leader_region_selector":"h1>a文本为现任领导的同容器p","name_selector":"b职务标签后的直系文本","duty_selector":"p>b","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"历任领导","include_selectors":["h1:has(a[href*=xrld]) + p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅配对每个b职务标签后的紧邻姓名文本。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验5组b标签—姓名文本。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"h1:has(a[href*=xrld]) + p"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    root=next((h.parent for h in soup.select('h1') if h.get_text(' ',strip=True)=='现任领导'),None);p=root.find('p') if root else None
    for b in p.find_all('b',recursive=False) if p else []:
        duty=re.sub(r"\s+","",b.get_text(" ",strip=True).rstrip('：:'));node=b.next_sibling
        while node is not None and (not isinstance(node,NavigableString) or not node.strip()):node=node.next_sibling
        name=re.sub(r"\s+","",str(node)) if node else ''
        if 2<=len(name)<=4 and name.isalpha() and duty:rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule['parser']),"selector_summary":"现任领导p的b职务标签与紧邻姓名文本"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
