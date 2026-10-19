from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0667",
    "page_type": "人物详情页",
    "structure_group": "lanzhou_gdb_single_profile_heading_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_gdb_single_profile_heading_duty_v1",
    "leader_region_selector": "table:has(.ldzw)",
    "name_selector": "table:has(.ldzw) h1",
    "duty_selector": ".ldzw p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "historical_list_to_detail_assumption_no_longer_matches_current_single_profile_entry",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "profile_table_selector": "table:has(.ldzw)",
            "name_selector": "h1",
            "duty_selector": ".ldzw p",
        },
        "api": {
            "enabled": False,
            "reason": "当前入口页在线HTML直接呈现一个人物详情，未发现历史脚本假定的人物目录链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从当前单人物详情卡片提取姓名和原始职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    duty_node = soup.select_one(".ldzw p")
    if duty_node is None:
        return []
    profile_table = duty_node.find_parent("table")
    name_node = profile_table.select_one("h1") if profile_table is not None else None
    if name_node is None:
        return []

    name = re.sub(r"\s+", "", normalize_space(name_node.get_text(" ", strip=True)))
    duty = normalize_space(duty_node.get_text(" ", strip=True))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
        return []
    return [
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "包含.ldzw的当前人物详情表格；h1姓名；.ldzw p原始职务；入口页本身不重复写入详情链接",
        }
    ]


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
