from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"3361","page_type":"人物列表完整页","structure_group":"zhejiang_department_leader_cards","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"list_direct","collector":"static_http","parser":"custom_zhejiang_medical_security_leader_cards_v2","leader_region_selector":".ld[data-showlist='2']","name_selector":".ld_tit","duty_selector":".jg_ldxx_item.ldzw .txt_item","detail_link_selector":".ld[data-showlist='2'] > a[href]","content_scope":{"start_anchor":"首张领导卡","end_anchor":"末张领导卡","include_selectors":[".ld[data-showlist='2'] > a[href]"],"exclude_selectors":["职责分工","医保业务","处室中心","页脚"]},"detail_strategy":{"required":False,"mode":"dynamic_link_from_card","detail_collector_type":"raw_http","detail_link_selector":".ld[data-showlist='2'] > a[href]","detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":10},"risk_flag":"卡片职责含医保业务和处室中心；仅取姓名与ldzw强字段","confidence":"high","profile_reusable":"","profile_judgement":"","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".ld[data-showlist='2']","name_selector":".ld_tit","duty_selector":".jg_ldxx_item.ldzw .txt_item","detail_link_selector":".ld[data-showlist='2'] > a[href]","content_scope":{"start_anchor":"首张领导卡","end_anchor":"末张领导卡","include_selectors":[".ld[data-showlist='2'] > a[href]"],"exclude_selectors":["职责分工","医保业务","处室中心","页脚"]}},"api":{"enabled":False,"reason":"静态卡片直接提供人物字段"}}}

def _clean(v:str)->str: return " ".join(str(v or "").replace("\u3000"," ").replace("\xa0"," ").split())
def _hidden(n:Tag)->bool:
    cur:Tag|None=n
    while cur is not None:
        style=str(cur.get("style","")).replace(" ","").lower(); classes={str(x).lower() for x in cur.get("class",[])}
        if cur.has_attr("hidden") or str(cur.get("aria-hidden","")).lower()=="true" or "display:none" in style or "visibility:hidden" in style or "hidden" in classes:return True
        if cur.name=="div" and "ld" in classes:return False
        cur=cur.parent if isinstance(cur.parent,Tag) else None
    return False

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser"); rows=[]; seen=set()
    for link in soup.select(".ld[data-showlist='2'] > a[href]"):
        if _hidden(link):continue
        nn=link.select_one(".ld_tit"); dn=link.select_one(".jg_ldxx_item.ldzw .txt_item")
        name=re.sub(r"\s+","",_clean(nn.get_text(" ",strip=True) if nn else "")); duty=_clean(dn.get_text(" ",strip=True) if dn else ""); href=str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}",name) or not duty or not href or name in seen:continue
        seen.add(name); rows.append({"name":name,"duty":duty,"detail_url":urljoin(final_url,href),"evidence":duty,"parser":"custom_zhejiang_medical_security_leader_cards_v2","selector_summary":"同卡姓名职务与外层详情"})
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals()); print(f"输出文件：{output_path}")
if __name__=="__main__":main()
