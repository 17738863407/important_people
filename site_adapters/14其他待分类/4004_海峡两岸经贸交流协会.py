from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
import requests
import urllib3
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4004","page_type":"协会领导文章入口页","structure_group":"aetats_leader_article","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_aetats_leader_article_v1","leader_region_selector":"文章详情正文","name_selector":"职务：姓名","duty_selector":"职务标签","detail_link_selector":"列表中的海贸会领导文章链接","content_scope":{"start_anchor":"海贸会领导","end_anchor":"免责声明","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_article_link"},"risk_flag":"入口列表不含具体人员，需动态读取“海贸会领导”文章；站点证书不匹配。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前文章采用重复的职务：姓名字段。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"name_selector":"文章正文文本"},"api":{"enabled":False,"reason":"当前HTML文章为权威来源"},"migration":{"verified_status":"verified"}}}

def clean_text(value:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",value or "").strip()
def fetch(url:str)->str:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning);s=requests.Session();s.trust_env=False;r=s.get(url,timeout=30,headers={"User-Agent":"Mozilla/5.0"},verify=False);r.raise_for_status();return r.content.decode("utf-8",errors="replace")
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");link=next((a for a in soup.find_all("a",href=True) if clean_text(a.get_text(" ",strip=True))=="海贸会领导"),None)
    detail_html=fetch(urljoin(final_url,link["href"])) if link is not None else html
    text=clean_text(BeautifulSoup(detail_html,"html.parser").get_text(" ",strip=True));rows=[]
    for duty,name in re.findall(r"((?:会\s*长)|(?:副\s*会\s*长)|秘书长)[：:]\s*([\u4e00-\u9fff\s]{2,6})(?=\s|商务部|$)",text):
        name=re.sub(r"\s+","",name);duty=re.sub(r"\s+","",duty)
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"海贸会领导文章职务：姓名"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
