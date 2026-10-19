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
    "rule_id": "4390",
    "page_type": "监察局领导之窗列表页",
    "structure_group": "fujian_mine_safety_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_fujian_mine_safety_leaders_v1",
    "leader_region_selector": "ul.lead_list",
    "name_selector": ".lead_name > p:first-child",
    "duty_selector": ".lead_name > p:nth-child(2)",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul.lead_list"], "exclude_selectors": [".lead_intro"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片含性别、民族、出生年月等简介，主职务仅取lead_name第二段",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验领导之窗5张卡片姓名和职务节点",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "ul.lead_list", "name_selector": ".lead_name > p:first-child", "duty_selector": ".lead_name > p:nth-child(2)", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["ul.lead_list"], "exclude_selectors": [".lead_intro"]}}, "api": {"enabled": False, "reason": "领导姓名和职务直接呈现在HTML卡片中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("ul.lead_list")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in root.select(":scope > li"):
        paragraphs = item.select(".lead_name > p")
        if len(paragraphs) < 2:
            continue
        name = clean_text(paragraphs[0].get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(paragraphs[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": "ul.lead_list>li .lead_name前两段"})
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
