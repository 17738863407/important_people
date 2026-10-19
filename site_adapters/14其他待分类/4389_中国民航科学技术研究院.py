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
    "rule_id": "4389",
    "page_type": "研究院领导成员卡片页",
    "structure_group": "castc_leader_member_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_castc_leader_members_v1",
    "leader_region_selector": ".news5 .con",
    "name_selector": "ul.hky_leader:not(.pcNone) .info h2",
    "duty_selector": "ul.hky_leader:not(.pcNone) .info p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".news5 .con"], "exclude_selectors": ["ul.hky_leader.pcNone"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "桌面端与移动端重复渲染后七人，排除pcNone移动列表并按桌面DOM顺序提取",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验桌面端5组共9名领导成员及多行职务",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".news5 .con", "name_selector": "ul.hky_leader:not(.pcNone) .info h2", "duty_selector": "ul.hky_leader:not(.pcNone) .info p", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".news5 .con"], "exclude_selectors": ["ul.hky_leader.pcNone"]}}, "api": {"enabled": False, "reason": "领导卡片直接呈现在HTML中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".news5 .con")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in root.select("ul.hky_leader:not(.pcNone) > li"):
        name_node = item.select_one(".info h2")
        duty_node = item.select_one(".info p")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty_parts = [clean_text(text) for text in duty_node.stripped_strings]
        duty = "；".join(part for part in duty_parts if part)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".news5桌面端ul.hky_leader领导卡片"})
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
