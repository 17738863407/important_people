from __future__ import annotations
import re,sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4015","page_type":"人民银行分行领导正文页","structure_group":"pbc_branch_leaders_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_pbc_shanxi_leaders_v1","leader_region_selector":"正文","name_selector":"领导段姓名","duty_selector":"同段剩余职务文本","detail_link_selector":"","content_scope":{"start_anchor":"中国人民银行山西省分行行领导","end_anchor":"法律声明","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"只取行领导段落。","confidence":"high","profile_reusable":False,"profile_judgement":"各人物均由独立段落给出姓名及职务。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");heading=soup.find(string=lambda v:v and "中国人民银行山西省分行行领导" in v);rows=[]
    for p in heading.find_all_next("p",limit=5) if heading else []:
        t=clean(p.get_text(" ",strip=True));m=re.match(r"([\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s+(.+)",t)
        if m:
            name=re.sub(r"\s+","",m.group(1));duty=m.group(2)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"行领导独立p段"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
