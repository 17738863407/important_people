from __future__ import annotations

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
    "rule_id": "3486",
    "page_type": "公司领导分组卡片页",
    "structure_group": "crhc_three_leader_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".page-box .leaders li",
    "name_selector": "lable.newBlank",
    "duty_selector": ".name p",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".page-box .leaders"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "党委、董事会、高级管理人员三组存在同一人物多职务卡片，按首次出现顺序去重并合并分组证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按首次出现顺序去重人物，动态合并其跨分组原始职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    group_names = [normalize_text(node.get_text(" ", strip=True)) for node in soup.select(".page-box .page-nav a")]
    groups = soup.select(".page-box .leaders")
    if len(group_names) != len(groups):
        raise ValueError(f"领导分组标题与内容数量不一致：{len(group_names)} != {len(groups)}")

    people: dict[str, dict[str, object]] = {}
    for group_name, group in zip(group_names, groups, strict=True):
        for card in group.select("li"):
            name_node = card.select_one("lable.newBlank")
            duty_node = card.select_one(".name p")
            name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
            duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            if not name or not duty:
                continue
            person = people.setdefault(name, {"duties": [], "evidence_parts": []})
            duties = person["duties"]
            evidence_parts = person["evidence_parts"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)
            evidence = f"{group_name}：{duty}"
            if isinstance(evidence_parts, list) and evidence not in evidence_parts:
                evidence_parts.append(evidence)

    rows: list[dict[str, str]] = []
    for name, person in people.items():
        duties = person["duties"]
        evidence_parts = person["evidence_parts"]
        if not isinstance(duties, list) or not isinstance(evidence_parts, list):
            continue
        combined_evidence = "；".join(str(item) for item in evidence_parts)
        rows.append(
            {
                "name": name,
                "duty": combined_evidence,
                "evidence": combined_evidence,
                "detail_url": "",
            }
        )
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
