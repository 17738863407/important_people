from __future__ import annotations
import re,sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4013","page_type":"清算所公司领导正文页","structure_group":"shclearing_leaders_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_shclearing_leaders_v1","leader_region_selector":"公司领导区域","name_selector":"姓名卡片","duty_selector":"职务卡片","detail_link_selector":"","content_scope":{"start_anchor":"银行间市场清算所股份有限公司领导","end_anchor":"新闻公告","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"页面正文含验证码模板字样，公共异常页检测会误判；内置解析器直接核验领导区域。","confidence":"high","profile_reusable":False,"profile_judgement":"当前领导姓名和职务依次呈现。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","locator":{"css":{"leader_region_selector":"公司领导区域"},"api":{"enabled":False,"reason":"当前HTML含领导数据"},"migration":{"verified_status":"verified"}}}
def clean(v:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",v or "").strip()
def fetch_live_html(url:str)->str:
    """直取当前原始HTML，避开页面验证码模板字样引发的公共误判。"""
    session=requests.Session();session.trust_env=False
    response=session.get(url,headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"},timeout=30)
    response.raise_for_status();response.encoding=response.apparent_encoding
    return response.text
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    if not html:html=fetch_live_html(str(page_rule["url"]))
    v=clean(BeautifulSoup(html,"html.parser").get_text(" ",strip=True));s=v.find("银行间市场清算所股份有限公司领导");e=v.find("新闻公告",s);p=v[s:e if e>s else None];rows=[]
    for name,duty in re.findall(r"([\u4e00-\u9fff]{2,4})\s+(党委[^\s]*|党委副书记、总经理|党委委员、(?:副总经理|纪委书记))",p):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"公司领导姓名+职务"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
