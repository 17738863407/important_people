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
    "rule_id": "4379",
    "page_type": "研究所现任领导简介列表页",
    "structure_group": "niglas_current_leader_profiles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_niglas_current_leaders_v1",
    "leader_region_selector": ".trs_editor_view > ul.pep-list",
    "name_selector": ".pep-txt > h1",
    "duty_selector": ".pep-txt > p:first-of-type",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view > ul.pep-list"], "exclude_selectors": [".pep-txt .trs_editor_view"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每人卡片内含完整履历，主职务仅取姓名标题后的直接首段",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验直接子级姓名和职务节点及人物顺序",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".trs_editor_view > ul.pep-list", "name_selector": ".pep-txt > h1", "duty_selector": ".pep-txt > p:first-of-type", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_editor_view > ul.pep-list"], "exclude_selectors": [".pep-txt .trs_editor_view"]}}, "api": {"enabled": False, "reason": "领导姓名和职务直接呈现在HTML简介列表中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".trs_editor_view > ul.pep-list")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in root.select(":scope > li"):
        name_node = item.select_one(":scope > .pep-txt > h1")
        duty_node = item.select_one(":scope > .pep-txt > p")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".trs_editor_view>ul.pep-list直接人物项"})
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
