from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4005","page_type":"基金会理事会正文页","structure_group":"teafund_board_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_teafund_board_text_v1","leader_region_selector":"#content","name_selector":"理事长、副理事长、秘书长正文名单","duty_selector":"职务标题","detail_link_selector":"","content_scope":{"start_anchor":"第七届理事会成员","end_anchor":"理 事（","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"同页包含上届任职及全体理事；仅当前理事长、副理事长、秘书长标题至理事标题之间的名单。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前文本职务分组。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文为权威来源"},"migration":{"verified_status":"verified"}}}
def text(value:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html,"html.parser");rows=[]
    for heading in soup.find_all("p"):
        duty=re.sub(r"\s+","",heading.get_text(" ",strip=True))
        if duty not in {"理事长","副理事长(以姓氏笔画为序）","秘书长"}:continue
        duty="副理事长" if duty.startswith("副理事长") else duty
        content=heading.find_next_sibling("p")
        while content is not None and not content.get_text(" ",strip=True):content=content.find_next_sibling("p")
        if content is None:continue
        for line in content.get_text("\n",strip=True).splitlines():
            line=line.replace("\u00a0"," ").strip();match=re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s{2,}",line)
            if match is None:continue
            name=re.sub(r"\s+","",match.group(1))
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}",name) and not any(x["name"]==name and x["duty"]==duty for x in rows):rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"第七届理事会职务标题及紧随换行名单"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
