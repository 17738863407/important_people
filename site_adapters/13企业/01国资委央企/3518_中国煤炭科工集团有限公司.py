from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3518",
    "page_type": "人物列表完整页",
    "structure_group": "煤科工管理团队分组与个人混合列表",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CctegGroupedManagementParser_v2",
    "leader_region_selector": ".asp-content .lead_list .lead_item",
    "name_selector": ".lead_name .span,.leader_name",
    "duty_selector": ".lead_job,.leader_job",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "原始HTML内容区为空，须浏览器渲染；同一人物可能在董事会与党委条目重复",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _own_text(node: object) -> str:
    return _compact_text(
        "".join(str(child) for child in node.children if isinstance(child, NavigableString))
    )


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析分组及个人条目，并按人物首次出现顺序聚合网页明确职务。"""
    soup = BeautifulSoup(html, "html.parser")
    duties_by_name: dict[str, list[str]] = {}

    def add_duty(name: str, duty: str) -> None:
        clean_name = _compact_text(name)
        clean_duty = _compact_text(duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", clean_name) or not clean_duty:
            return
        duties = duties_by_name.setdefault(clean_name, [])
        if clean_duty not in duties:
            duties.append(clean_duty)

    for item in soup.select(".asp-content .lead_list .lead_item"):
        group_duty_node = item.select_one(":scope > .lead_job")
        grouped_names = item.select(":scope > .lead_name .span")
        if group_duty_node is not None and grouped_names:
            group_duty = _own_text(group_duty_node) or _compact_text(
                group_duty_node.get_text(" ", strip=True)
            )
            for name_node in grouped_names:
                add_duty(name_node.get_text(" ", strip=True), group_duty)
            continue
        for name_node in item.select(".leader_name"):
            duty_node = name_node.find_next_sibling(class_="leader_job")
            if duty_node is None:
                continue
            duty = _own_text(duty_node) or _compact_text(duty_node.get_text(" ", strip=True))
            add_duty(name_node.get_text(" ", strip=True), duty)

    records: list[dict] = []
    for name, duties in duties_by_name.items():
        evidence = "；".join(duties)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "lead_item；分组span或leader_name；对应job；按人物聚合",
            }
        )
    if not records:
        raise RuntimeError("煤科工管理团队渲染DOM未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
