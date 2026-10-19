from __future__ import annotations
import html as html_lib
import re
import sys
from collections import OrderedDict
from pathlib import Path
import requests

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4499",
    "page_type": "纪委监委领导机构动态接口",
    "structure_group": "heilongjiang_discipline_supervision_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "extract_mode": "custom",
    "parser": "page_heilongjiang_discipline_supervision_api_v1",
    "leader_region_selector": "/HljjjjcServer/leaderUser/listNews",
    "name_selector": "result.data.name",
    "duty_selector": "result.param.listDictionary + leader_classify",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员名单；页面无法在线核验时明确失败。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    api_url="https://www.hljjjjc.gov.cn/HljjjjcServer/leaderUser/listNews"
    response=requests.post(api_url,data={"first_classify_sign":"xxgk","second_classify_sign":"ldbz"},timeout=30,verify=False)
    response.raise_for_status(); payload=response.json(); result=payload.get("result") or {}
    data=result.get("data") or []; dictionaries=(result.get("param") or {}).get("listDictionary") or []
    by_sort={str(item.get("dictionarySort")):item for item in dictionaries}
    role_specs=[("101","书记"),("102","副书记"),("103","常委"),("202","主任"),("201","代主任"),("203","副主任")]
    people: OrderedDict[str,list[str]]=OrderedDict()
    for sort_code,role in role_specs:
        info=by_sort.get(sort_code)
        if not info: continue
        class_id=str(info.get("dictionaryId") or "")
        subject_info=by_sort.get("1" if sort_code.startswith("1") else "2") or {}
        subject=re.sub(r"\s+","",str(subject_info.get("dictionaryName") or ("中共黑龙江省纪律检查委员会" if sort_code.startswith("1") else "黑龙江省监察委员会")))
        duty=subject+role
        for item in data:
            if class_id and class_id in str(item.get("leader_classify") or ""):
                name=html_lib.unescape(str(item.get("name") or "")); name=re.sub(r"[（(].*?[）)]|\s+","",name)
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}",name): continue
                duties=people.setdefault(name,[])
                if duty not in duties: duties.append(duty)
    rows=[]
    for name,duties in people.items():
        evidence="；".join(duties); rows.append({"name":name,"duty":evidence,"evidence":evidence,"detail_url":"","parser":str(page_rule.get("parser","")),"selector_summary":"leaderUser/listNews分类字典101/102/103/201/202/203；排除104/204委员"})
    if not rows: raise RuntimeError("实时领导接口未提取到目标领导")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
