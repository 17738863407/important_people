from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4064","page_type":"研究所领导列表页","structure_group":"ib_bai14_li_v1","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ib_bai14_li_v1","leader_region_selector":"li.bai14:has(a)","name_selector":"a","duty_selector":"li直系文本","detail_link_selector":"a[href$='.html']","content_scope":{"start_anchor":"现任领导","end_anchor":"版权所有","include_selectors":["li.bai14:has(a)"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"card_link"},"risk_flag":"所长中的空格为排版空白，确定性压缩。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验6行姓名链接与冒号后职务。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"li.bai14:has(a)"},"api":{"enabled":False,"reason":"HTML列表完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for li in soup.select("li.bai14:has(a)"):
        a=li.select_one("a[href]");t=li.get_text(" ",strip=True)
        if not a:continue
        n=a.get_text(" ",strip=True);v=re.sub(r"\s+","",t[len(n):].lstrip().lstrip("：:"))
        if 2<=len(n)<=4 and n.isalpha() and v:rows.append({"name":n,"duty":v,"detail_url":a["href"],"evidence":v,"parser":str(page_rule["parser"]),"selector_summary":"现任领导bai14列表行"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
