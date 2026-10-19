from __future__ import annotations
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3649","domain":"www.zju.edu.cn","page_type":"现任领导内嵌JSON","structure_group":"zju_embedded_leaders_json_v47","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"embedded_json_groups","collector":"static_http","parser":"page_zju_current_leaders_v1","leader_region_selector":"#wp_content_w85_0","name_selector":"json.people.name","duty_selector":"json.typeName","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"merge_repeated_names_across_json_groups","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """解析页面内嵌的领导分组JSON，按数组顺序合并重复人物。"""
    soup=BeautifulSoup(html,"html.parser");node=soup.select_one("#wp_content_w85_0")
    if node is None:return []
    try:data=json.loads(node.get_text())
    except (TypeError,ValueError,json.JSONDecodeError):return []
    ordered=[];by_name={}
    for group in data if isinstance(data,list) else []:
        duty=clean(group.get("typeName","")) if isinstance(group,dict) else ""
        for person in group.get("people",[]) if isinstance(group,dict) else []:
            name=clean(person.get("name","")) if isinstance(person,dict) else ""
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) or not duty:continue
            if name not in by_name:by_name[name]=[];ordered.append(name)
            if duty not in by_name[name]:by_name[name].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]),"evidence":"；".join(by_name[name]),"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；region=#wp_content_w85_0；json_fields=typeName+people[].name"} for name in ordered]

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
