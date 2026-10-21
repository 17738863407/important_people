from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4507", "page_type": "纪委监委领导机构定义列表页",
    "structure_group": "ningxia_discipline_supervision_dl_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_ningxia_discipline_supervision_dl_v1",
    "leader_region_selector": "section.content.lead", "name_selector": "dl dd li .art a, dl dd li .art",
    "duty_selector": "dl dd li .name b", "detail_link_selector": "dl dd li .art a[href]",
    "detail_strategy": {"required": False, "mode": "person_anchor"}, "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任，排除两个委员分组。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("section.content.lead")
    if region is None:
        raise RuntimeError("未找到领导机构正文 section.content.lead")
    people: OrderedDict[str, dict[str, object]] = OrderedDict()
    role_map = {"书记": "书记", "副书记": "副书记", "常务委员会委员": "常委", "主任": "主任", "副主任": "副主任"}
    for group in region.select(":scope > dl"):
        heading = group.find("dt")
        subject = compact(heading.get_text(" ", strip=True)) if heading else ""
        if not subject:
            continue
        for item in group.select("dd li"):
            role_node = item.select_one(".name b")
            role = role_map.get(compact(role_node.get_text(" ", strip=True)) if role_node else "")
            if not role:
                continue
            art = item.select_one(".art")
            if art is None:
                continue
            anchors = art.select("a[href]")
            candidates = anchors or [art]
            for node in candidates:
                name = compact(node.get_text(" ", strip=True))
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                    continue
                duty = subject + role
                entry = people.setdefault(name, {"duties": [], "detail_url": ""})
                duties = entry["duties"]
                if isinstance(duties, list) and duty not in duties:
                    duties.append(duty)
                if node.name == "a" and node.get("href"):
                    entry["detail_url"] = urljoin(final_url, str(node["href"]))
                elif item.find("a", href=True):
                    entry["detail_url"] = urljoin(final_url, str(item.find("a", href=True)["href"]))
    rows = []
    for name, entry in people.items():
        duties = entry["duties"]
        evidence = "；".join(duties) if isinstance(duties, list) else ""
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": str(entry["detail_url"]), "parser": str(page_rule.get("parser", "")), "selector_summary": "section.content.lead > dl；li职务分组；排除委员"})
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
