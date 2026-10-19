from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
def resolve_project_dir()->Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4007","page_type":"研究会理事会正文页","structure_group":"cfcra_board_text","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cfcra_board_text_v1","leader_region_selector":"正文","name_selector":"第六届负责人名单","duty_selector":"会长、副会长、秘书长、监事标签","detail_link_selector":"","content_scope":{"start_anchor":"第六届负责人名单","end_anchor":"研究会概况","include_selectors":[],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"仅提取第六届负责人名单，排除正文联系人。","confidence":"high","profile_reusable":False,"profile_judgement":"当前正文用稳定职务标签列出负责人。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":"正文"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}
def clean(value:str)->str:return re.sub(r"[\s\u00a0\u3000]+"," ",value or "").strip()
def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    value=clean(BeautifulSoup(html,"html.parser").get_text(" ",strip=True));start=value.find("中国食文化研究会第六届负责人名单");end=value.find("研究会概况",start);part=value[start:end];rows=[]
    for duty,pattern in [("会长",r"会长[:：]\s*([\u4e00-\u9fff]{2,4})"),("副会长",r"副会长[:：]\s*([^秘监]+)"),("秘书长",r"秘书长[:：]\s*([\u4e00-\u9fff]{2,4})"),("监事",r"监事[:：]\s*([^研究]+)")]:
        m=re.search(pattern,part)
        if not m:continue
        for name in re.findall(r"[\u4e00-\u9fff]{2,4}",m.group(1)):
            if name in {"法人代表","监事长"}:continue
            rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule.get("parser","")),"selector_summary":"第六届负责人名单职务标签"})
    return rows
def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=="__main__":main()
