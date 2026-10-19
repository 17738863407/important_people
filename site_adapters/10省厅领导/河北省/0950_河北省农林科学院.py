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
    "rule_id": "0950",
    "page_type": "人物列表完整页",
    "structure_group": "hebnky_datalist_spaced_fields",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebnky_datalist_spaced_fields_v1",
    "leader_region_selector": "#MainContent_DataList1",
    "name_selector": ":scope > tr > td td[style]文本第一字段",
    "duty_selector": ":scope > tr > td td[style]文本第二字段",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "院领导",
        "end_anchor": "",
        "include_selectors": ["#MainContent_DataList1"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "姓名、职务和职责以连续文本及多空格分隔；仅取DataList每行前两个字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#MainContent_DataList1",
            "name_selector": ":scope > tr > td td[style]文本第一字段",
            "duty_selector": ":scope > tr > td td[style]文本第二字段",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "院领导",
                "end_anchor": "",
                "include_selectors": ["#MainContent_DataList1"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML DataList按行直接包含姓名、职务和职责"},
    },
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按DataList原始行顺序读取多空格分隔的姓名与职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#MainContent_DataList1")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in scope.select(":scope > tr > td") if scope else []:
        field = item.select_one("td[style]")
        raw_text = field.get_text(" ", strip=True) if field else ""
        parts = [part for part in re.split(r"[\s\u00a0]{3,}", raw_text) if part.strip()]
        if len(parts) < 2:
            continue
        name = _compact_text(parts[0])
        duty = _compact_text(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_hebnky_datalist_spaced_fields_v1",
                "selector_summary": "#MainContent_DataList1直接行；多空格分隔的前两字段为姓名、职务",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
