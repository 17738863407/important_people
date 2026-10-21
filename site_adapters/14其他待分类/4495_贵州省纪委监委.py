from __future__ import annotations
import re
import sys
from collections import OrderedDict
from pathlib import Path
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4495",
    "page_type": "纪委监委领导机构分组页",
    "structure_group": "guizhou_discipline_supervision_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_guizhou_discipline_supervision_groups_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": "目标职务p中strong后的文本",
    "duty_selector": "p > strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员名单；页面无法在线核验时明确失败。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup=BeautifulSoup(html or "","html.parser"); region=soup.select_one(".trs_editor_view")
    if region is None: raise RuntimeError("未找到领导机构正文")
    subject=""; people: OrderedDict[str,list[str]]=OrderedDict()
    for p in region.find_all("p",recursive=False):
        strong=p.find("strong"); label=re.sub(r"\s+","",strong.get_text(" ",strip=True)) if strong else ""
        if "纪律检查委员会" in label: subject=label; continue
        if label=="贵州省监察委员会": subject=label; continue
        if "委员" in label and label!="常务委员会委员": continue
        role={"书记":"书记","副书记":"副书记","常务委员会委员":"常委","主任":"主任","副主任":"副主任"}.get(label)
        if not role or not subject: continue
        strong.extract(); raw=p.get_text(" ",strip=True); raw=re.sub(r"[（(][^）)]*[）)]","",raw)
        names=[re.sub(r"\s+","",x) for x in re.split(r"[\s\u2002\u3000]+",raw) if re.fullmatch(r"[\u3400-\u9fff·]{2,6}",re.sub(r"\s+","",x))]
        duty=subject+role
        for name in names:
            duties=people.setdefault(name,[])
            if duty not in duties: duties.append(duty)
    rows=[]
    for name,duties in people.items():
        evidence="；".join(duties); rows.append({"name":name,"duty":evidence,"evidence":evidence,"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":".trs_editor_view直属p职务分组；排除委员"})
    if not rows: raise RuntimeError("未提取到目标纪委监委领导")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
