from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3997", "page_type": "研究院核心团队卡片页", "structure_group": "caupd_core_team_cards", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_caupd_core_team_cards_v1",
    "leader_region_selector": "#survey3 .tab-item .list", "name_selector": ".item .h", "duty_selector": ".item .p1", "detail_link_selector": "a[href*='/figure/hexin/detail/']",
    "content_scope": {"start_anchor": "核心团队", "end_anchor": "总工团队", "include_selectors": ["#survey3"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "dynamic_card_link"}, "risk_flag": "同页另有总工团队；仅核心团队的第一个卡片列表属于本机构领导。",
    "confidence": "high", "profile_reusable": False, "profile_judgement": "已核验核心团队卡片内姓名、职务和独立人物链接的对应关系。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#survey3 .tab-item .list", "name_selector": ".item .h", "duty_selector": ".item .p1", "detail_link_selector": "a[href*='/figure/hexin/detail/']"}, "api": {"enabled": False, "reason": "当前HTML卡片已提供结构化领导字段"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只读取“核心团队”锚点下首个卡片列表，保持页面卡片顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one("#survey3")
    root = anchor.select_one(".tab-item .list") if anchor else None
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    for card in root.select(":scope > .item"):
        name_node, duty_node, link = card.select_one(".h"), card.select_one(".p1"), card.select_one("a[href*='/figure/hexin/detail/']")
        name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty_parts = [part for part in (clean_text(item) for item in (duty_node.stripped_strings if duty_node else [])) if part and part != "中国城市规划设计研究院"]
        duty = " ".join(duty_parts)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")) if link else "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": "#survey3核心团队 .item .h/.p1"})
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
