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
    "rule_id": "4384",
    "page_type": "联合中心工作人员卡片页",
    "structure_group": "cslcer_admin_staff_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cslcer_directors_v1",
    "leader_region_selector": ".personnel-content",
    "name_selector": ".personnelItem_text_name",
    "duty_selector": ".personnelItem_text > p:nth-of-type(2)",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".personnel-content"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时列出主管、秘书和助理，只抽取职务明确包含主任的领导人员",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验工作人员卡片中的主任、外方主任、执行主任和副主任",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".personnel-content", "name_selector": ".personnelItem_text_name", "duty_selector": ".personnelItem_text > p:nth-of-type(2)", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".personnel-content"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "工作人员卡片直接呈现在HTML中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def extract_display_name(value: str) -> str:
    text = clean_text(value)
    chinese_match = re.match(r"^([\u3400-\u9fff]{1,2}(?:\s*[\u3400-\u9fff]){1,4})", text)
    if chinese_match:
        return chinese_match.group(1).replace(" ", "")
    return text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".personnel-content")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in root.select(".personnelItem"):
        text_root = card.select_one(".personnelItem_text")
        name_node = card.select_one(".personnelItem_text_name")
        direct_paragraphs = text_root.find_all("p", recursive=False) if text_root else []
        if name_node is None or len(direct_paragraphs) < 2:
            continue
        name = extract_display_name(name_node.get_text(" ", strip=True))
        duty = clean_text(direct_paragraphs[1].get_text(" ", strip=True))
        if "主任" not in duty or not name or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".personnel-content人员卡片中职务含主任者"})
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
