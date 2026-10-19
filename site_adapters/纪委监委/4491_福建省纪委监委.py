from __future__ import annotations
import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE={"rule_id":"4491","page_type":"纪委监委领导机构分组页","structure_group":"fujian_discipline_supervision_groups_v1","reuse_scope":"single_page","load_mode":"静态HTML","extract_mode":"custom","parser":"page_fujian_discipline_supervision_groups_v1","leader_region_selector":".wz-text #Info_Content","name_selector":"目标职务段落a[href]","duty_selector":"strong/b职务标题","detail_link_selector":"目标段落a[href]","detail_strategy":{"required":False,"mode":"direct_links"},"locator_strategy":"custom_parse_page","confidence":"high","filter_policy":"strong_no_wordlist","risk_flag":"只取纪委书记、副书记、常委及监委主任/代理主任、副主任；排除纪委委员和监委委员。"}

def clean(value: object) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", "", str(value or ""))

def parse_page(html:str,final_url:str,page_rule:dict[str,object])->list[dict[str,str]]:
    soup=BeautifulSoup(html or "","html.parser"); region=soup.select_one(".wz-text #Info_Content")
    if region is None: raise RuntimeError("未找到领导机构正文")
    people: OrderedDict[str,dict[str,object]]=OrderedDict(); subject=""; pending_role=""
    for p in region.find_all("p"):
        text=clean(p.get_text(" ",strip=True))
        if "中国共产党福建省" in text and "纪律检查委员会" in text: subject="中国共产党福建省第十一届纪律检查委员会"; pending_role=""; continue
        if text=="福建省监察委员会": subject="福建省监察委员会"; pending_role=""; continue
        label_node=p.find(["strong","b"]); label=clean(label_node.get_text(" ",strip=True)) if label_node else ""
        if "委员" in label and "常务委员会委员" not in label: pending_role=""; continue
        role=""
        if label in {"书记：","副书记：","常务委员会委员：","主任：","代理主任：","副主任："}: role=label.rstrip("：")
        elif pending_role: role=pending_role
        if label=="常务委员会委员：" and not p.find("a"): pending_role="常务委员会委员"; continue
        if label and label!="常务委员会委员：": pending_role=""
        if not subject or not role: continue
        duty=subject+("常委" if role=="常务委员会委员" else role)
        for link in p.select("a[href]"):
            name=re.sub(r"[（(].*?[）)]","",clean(link.get_text(" ",strip=True)))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}",name): continue
            rec=people.setdefault(name,{"duties":[],"detail_url":urljoin(final_url,link.get("href",""))})
            if duty not in rec["duties"]: rec["duties"].append(duty)
    rows=[]
    for name,rec in people.items():
        evidence="；".join(rec["duties"]); rows.append({"name":name,"duty":evidence,"evidence":evidence,"detail_url":rec["detail_url"],"parser":str(page_rule.get("parser","")),"selector_summary":".wz-text目标领导职务段落；排除委员段落"})
    if not rows: raise RuntimeError("未提取到目标纪委监委领导")
    return rows

def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE,globals())}")

if __name__=="__main__": main()
