from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4039","page_type":"脚本跳转的领导正文页","structure_group":"cas_js_redirect_leaders","reuse_scope":"single_page","load_mode":"静态HTML加JS跳转","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cas_audit_js_redirect_leaders_v1","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","leader_region_selector":"跳转后正文现任领导段","name_selector":"职务标签后姓名","duty_selector":"同段职务标题","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"附件","include_selectors":["正文p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"入口仅含location.replace；主任身份在同一职务标签中保留。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验跳转目标的实时职务—姓名文本。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文现任领导段"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    s=requests.Session();s.trust_env=False;entry=s.get(str(page_rule["url"]),timeout=30,headers={"User-Agent":"Mozilla/5.0"});entry.raise_for_status();m=re.search(r"location\.replace\(\s*[\"']([^\"']+)",entry.text);res=s.get(urljoin(entry.url,m.group(1)) if m else entry.url,timeout=30,headers={"User-Agent":"Mozilla/5.0"});res.raise_for_status();text=BeautifulSoup(res.content,"html.parser").get_text(" ",strip=True);rows=[]
    for duty,names in re.findall(r"(局\s*长\s*\(\s*主\s*任\s*\))\s*[：:]\s*([\u4e00-\u9fff\s 、，,]+?)(?=\s*副\s*局|附件)",text)+re.findall(r"(副\s*局\s*长\s*(?:\([^)]*\))?)\s*[：:]\s*([\u4e00-\u9fff\s 、，,]+?)(?=附件|$)",text):
        duty=re.sub(r"\s+","",duty)
        for name in re.split(r"[、，,]",names):
            name=re.sub(r"\s+","",name)
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"跳转后现任领导正文职务—姓名文本"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
