from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3512",
    "page_type": "集团领导分组卡片页",
    "structure_group": "xxcig_group_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": "#ejcon0 dl.ldList img[alt]",
    "name_selector": "img[alt]",
    "duty_selector": "p > em",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["#ejcon0 dl.ldList"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "党委常委、董事会成员、经理层成员分组含同一人物重复卡片，按首次出现顺序去重并合并分组证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按首次出现顺序去重人物，动态合并其跨分组原始职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    people: dict[str, list[str]] = {}
    for section in soup.select("#ejcon0 .portlet"):
        group_node = section.select_one(".mk_title h2 .on")
        group_name = normalize_text(group_node.get_text(" ", strip=True) if group_node else "")
        leader_list = section.select_one("dl.ldList")
        if not group_name or leader_list is None:
            continue
        for image in leader_list.select("img[alt]"):
            card = image.find_parent(["div", "dt", "dd"])
            duty_node = card.find("em") if card else None
            name = re.sub(r"\s+", "", str(image.get("alt") or ""))
            duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
                continue
            evidence = f"{group_name}：{duty}"
            evidence_parts = people.setdefault(name, [])
            if evidence not in evidence_parts:
                evidence_parts.append(evidence)

    rows: list[dict[str, str]] = []
    for name, evidence_parts in people.items():
        evidence = "；".join(evidence_parts)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": ""})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
