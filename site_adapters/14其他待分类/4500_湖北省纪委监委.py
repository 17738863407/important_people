from __future__ import annotations
import re
import sys
from collections import OrderedDict
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4500",
    "page_type": "纪委监委正文分组名单",
    "structure_group": "hubei_discipline_supervision_article_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "grouped_article",
    "parser": "page_hubei_discipline_supervision_article_groups_v1",
    "leader_region_selector": "领导机构信息至领导个人简历前的正文p",
    "name_selector": "",
    "duty_selector": "",
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
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    people: OrderedDict[str, list[str]] = OrderedDict()
    section = ""
    for paragraph in soup.select("p"):
        text = re.sub(r"[\s\u3000\xa0]+", "", paragraph.get_text(" ", strip=True))
        if text == "领导个人简历":
            break
        if "纪律检查委员会" in text and "委员（" not in text:
            section = text
            continue
        if text == "湖北省监察委员会":
            section = text
            continue
        match = re.fullmatch(r"(书记|副书记|常务委员会委员|主任|副主任)：(.+)", text)
        if match is None:
            continue
        role, names_text = match.groups()
        target = ("纪律检查委员会" in section and role in {"书记", "副书记", "常务委员会委员"}) or (section == "湖北省监察委员会" and role in {"主任", "副主任"})
        if not target:
            continue
        for raw_name in names_text.split("、"):
            name = re.sub(r"[（(].*?[）)]", "", raw_name)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
                continue
            duty = section + role
            duties = people.setdefault(name, [])
            if duty not in duties:
                duties.append(duty)
    rows = [{"name": name, "duty": "；".join(duties), "evidence": "；".join(duties), "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": "正文纪委/监委目标职务分组"} for name, duties in people.items()]
    if not rows:
        raise RuntimeError("领导机构分组未提取到目标人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
