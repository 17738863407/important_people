from __future__ import annotations
import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {"rule_id": "4492", "page_type": "纪委监委分组领导列表",
    "structure_group": "gansu_discipline_supervision_groups_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "extract_mode": "grouped_list",
    "parser": "page_gansu_discipline_supervision_groups_v1", "leader_region_selector": ".leader-box",
    "name_selector": ".leader-list .leader-item a[href]", "duty_selector": "h2与h4分组标题",
    "detail_link_selector": "同一人物a[href]", "detail_strategy": {"required": False, "mode": "dynamic_link"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员和秘书长分组；同人职务按网页顺序合并"}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    if not html:
        response = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        html = response.content.decode("utf-8")
        final_url = response.url
    soup = BeautifulSoup(html or "", "html.parser")
    box = soup.select_one(".leader-box")
    if box is None:
        raise RuntimeError("领导机构页缺少 .leader-box")
    people: OrderedDict[str, dict[str, object]] = OrderedDict()
    section = ""
    for node in box.children:
        if not isinstance(node, Tag):
            continue
        if node.name == "h2":
            section = re.sub(r"\s+", "", node.get_text(" ", strip=True)).lstrip("\ufeff")
            continue
        if "leader-list" not in (node.get("class") or []):
            continue
        role_node = node.select_one("h4")
        role = re.sub(r"\s+", "", role_node.get_text(" ", strip=True) if role_node else "")
        target = ("纪律检查委员会" in section and role in {"书记", "副书记", "常务委员会委员"}) or (
            "监察委员会" in section and "纪律检查委员会" not in section and role in {"主任", "副主任"})
        if not target:
            continue
        duty = section + role
        for link in node.select(".leader-item a[href]"):
            name = re.sub(r"[（(].*?[）)]", "", re.sub(r"\s+", "", link.get_text(" ", strip=True)))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
                continue
            record = people.setdefault(name, {"duties": [], "detail_url": urljoin(final_url, str(link.get("href") or ""))})
            duties = record["duties"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)
    rows = []
    for name, record in people.items():
        evidence = "；".join(record["duties"])
        rows.append({"name": name, "duty": evidence, "evidence": evidence,
            "detail_url": str(record["detail_url"]), "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": ".leader-box内纪委书记/副书记/常委及监委主任/副主任"})
    if not rows:
        raise RuntimeError("目标领导分组未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
