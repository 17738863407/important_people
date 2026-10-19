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
    "rule_id": "4511", "page_type": "纪委监委领导机构分组页",
    "structure_group": "shaanxi_discipline_supervision_spans_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_shaanxi_discipline_supervision_spans_v1",
    "leader_region_selector": ".ldjg", "name_selector": ".content2 .spa4, .content2 .spa2",
    "duty_selector": ".content2 .spa1", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；秘书长与委员分组排除。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".ldjg")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .ldjg")
    subject = ""
    people: OrderedDict[str, list[str]] = OrderedDict()
    role_map = {"书记": "书记", "副书记": "副书记", "常务委员会委员": "常委", "主任": "主任", "副主任": "副主任"}
    for node in region.find_all(["h2", "div"], recursive=False):
        if node.name == "h2":
            subject = compact(node.get_text(" ", strip=True))
            continue
        if "content2" not in (node.get("class") or []) or not subject:
            continue
        role = role_map.get(compact("".join(x.get_text(" ", strip=True) for x in node.select(".spa1"))))
        if not role:
            continue
        duty = subject + role
        for person in node.select(".spa4, .spa2"):
            name = compact(re.sub(r"[（(].*?[）)]", "", person.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                continue
            duties = people.setdefault(name, [])
            if duty not in duties:
                duties.append(duty)
    rows = []
    for name, duties in people.items():
        evidence = "；".join(duties)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".ldjg直属h2及.content2；spa1职务；排除秘书长和委员"})
    if not rows:
        raise RuntimeError("未提取到目标纪委监委领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
