from __future__ import annotations
import re,sys
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import requests
from bs4 import BeautifulSoup

def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4028","page_type":"总局分支SPA文章页","structure_group":"nfra_static_docclob","reuse_scope":"single_page","load_mode":"接口JSON","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_nfra_static_docclob_token_heading_v2","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","leader_region_selector":"接口data.docClob中的现任领导段","name_selector":"段首冒号前末尾姓名词组","duty_selector":"现任句完整现职","detail_link_selector":"","content_scope":{"start_anchor":"局领导","end_anchor":"文档末尾","include_selectors":["data.docClob p"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"当前页面姓名含不规则逐字空格并混用全角、半角冒号。","confidence":"high","profile_reusable":True,"profile_judgement":"已核验静态JSON中同段包含段首姓名及现任职务句。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"api":{"enabled":True,"endpoint":"/cn/static/data/DocInfo/SelectDocEntityByItemId/data_itemId={itemId}.json","params":{"itemId":"入口查询参数"},"data_path":"data.docClob"},"migration":{"verified_status":"verified"}}}

def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    entry=str(page_rule["url"]);item_id=parse_qs(urlsplit(entry).query).get("itemId",[""])[0];u=urlsplit(entry);api=f"{u.scheme}://{u.netloc}/cn/static/data/DocInfo/SelectDocEntityByItemId/data_itemId={item_id}.json";s=requests.Session();s.trust_env=False;r=s.get(api,timeout=30,headers={"User-Agent":"Mozilla/5.0"});r.raise_for_status();doc=r.json().get("data",{}).get("docClob","");rows=[]
    for p in BeautifulSoup(doc,"html.parser").select("p"):
        raw=p.get_text(" ",strip=True);prefix=re.split(r"[：:]",raw,1)[0];tokens=prefix.split();name=tokens[-1] if tokens else ""
        if len(name)==1 and len(tokens)>=2 and re.fullmatch(r"[\u4e00-\u9fff]{1,3}",tokens[-2]):name=tokens[-2]+name
        e=re.search(r"现任\s*(.+?)[。．]",raw)
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and e:
            duty=re.sub(r"\s+","",e.group(1));rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"静态JSON data.docClob现任领导段"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
