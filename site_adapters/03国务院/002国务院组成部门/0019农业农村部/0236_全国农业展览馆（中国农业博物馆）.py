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
    "rule_id": "0236", "page_type": "多人物详情合并页", "structure_group": "ciae_leadership_cards_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ciae_leadership_cards_v2",
    "leader_region_selector": "div.leadership1 div.li", "name_selector": "div.name", "duty_selector": "div.p comma_prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.leadership1"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "每卡p字段为职务加人口信息；仅按首个逗号确定性截取卡片开头职务原文", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_profile_prefix_cards",
    "locator": {"css": {"leader_region_selector": "div.leadership1 div.li", "name_selector": "div.name", "duty_selector": "div.p before first comma"}, "api": {"enabled": False, "reason": "当前静态HTML领导卡片直接提供姓名及职务简介"}, "migration": {"source": "legacy_business_source_and_offline_dependency_removed", "verified_status": "verified_current_raw_http", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(page_rule["leader_region_selector"]):
        name_node, profile_node = card.select_one("div.name"), card.select_one("div.p")
        if name_node is None or profile_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        profile = clean_text(profile_node.get_text(" ", strip=True))
        duty = clean_text(re.split(r"[，,。；;]", profile, maxsplit=1)[0])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=current_profile_card；boundary=first_comma；order=card_dom"})
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
