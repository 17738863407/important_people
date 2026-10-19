from __future__ import annotations
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup

PAGE_RULE={"rule_id":"3624","domain":"www.uibe.edu.cn","page_type":"现任领导职务分组卡片","structure_group":"uibe_leader_groups_2026","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"online","extract_mode":"group_title_name","collector":"static_http","parser":"page_uibe_current_leaders_v1","leader_region_selector":".sub_013a","name_selector":".box>a>.txt","duty_selector":".sub_title","detail_link_selector":"","detail_strategy":{"required":False,"mode":"none","candidate_links":[]},"risk_flag":"exclude_biography_and_responsibilities","confidence":"high","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page"}

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(text:str)->str:
    """清理纯排版空白。"""
    return re.sub(r"\s+","",str(text or "").replace("\u3000"," ").replace("\xa0"," ")).strip("：:")

def parse_page(html:str,final_url:str,page_rule:dict)->list[dict[str,str]]:
    """按页面职务分组顺序提取，并合并同一人物的各项当前职务。"""
    soup=BeautifulSoup(html,"html.parser");ordered=[];by_name={}
    for group in soup.select(".sub_013a"):
        d=group.select_one(".sub_title");duty=clean(d.get_text(" ",strip=True) if d else "")
        for n in group.select(".box>a>.txt"):
            link=n.find_parent("a");vice=link.select_one(".vicetitle") if link else None
            name=clean(n.get_text(" ",strip=True));profile_duty=clean(vice.get_text(" ",strip=True) if vice else "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty:
                if name not in by_name:by_name[name]=[];ordered.append(name)
                if profile_duty and profile_duty not in by_name[name]:by_name[name].append(profile_duty)
                if duty not in profile_duty and duty not in by_name[name]:by_name[name].append(duty)
    return [{"name":name,"duty":"；".join(by_name[name]),"evidence":"；".join(by_name[name]),"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"strategy=custom_parse_page；group=.sub_013a；fields=.sub_title+.box>a>.txt+.vicetitle"} for name in ordered]

def main()->None:
    """运行当前页面级在线爬虫。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};output_path=run_page_adapter(PAGE_RULE,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    main()
