from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理字段排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导介绍列表项提取首行独立姓名和职务，排除分管工作。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("table.gl_con td[valign='top']:last-child ul > li"):
        first_line = item.find("div", recursive=False)
        fields = first_line.find_all("div", recursive=False) if first_line else []
        if len(fields) < 2:
            continue
        name = re.sub(r"\s+", "", fields[0].get_text(" ", strip=True))
        duty = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_drug_leader_list_v2",
                "selector_summary": "leader=table.gl_con右侧ul>li；name=首行第1直属div；duty=首行第2直属div；detail=none",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3281",
    "page_type": "人物表格页",
    "structure_group": "qinghai_drug_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_drug_leader_list_v2",
    "leader_region_selector": "table.gl_con td[valign='top']:last-child ul > li",
    "name_selector": "首行第1直属div",
    "duty_selector": "首行第2直属div",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导介绍",
        "end_anchor": "",
        "include_selectors": ["table.gl_con td[valign='top']:last-child"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "table.gl_con td[valign='top']:last-child ul > li",
            "name_selector": "首行第1直属div",
            "duty_selector": "首行第2直属div",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导介绍",
                "end_anchor": "",
                "include_selectors": ["table.gl_con td[valign='top']:last-child"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML领导列表项已提供独立姓名和职务字段"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
