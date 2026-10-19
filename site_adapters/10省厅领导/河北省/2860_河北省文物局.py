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
    "rule_id": "2860",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_cultural_relics_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_cultural_relics_leader_cards_v1",
    "leader_region_selector": ".contentRight .itemBox",
    "name_selector": ".item2 > div > p",
    "duty_selector": ".item2 > div > div",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": [".contentRight .itemBox"], "exclude_selectors": [".item2 span"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "卡片span为职责分工，仅提取p姓名和直接div职务字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".contentRight .itemBox", "name_selector": ".item2 > div > p", "duty_selector": ".item2 > div > div", "detail_link_selector": "", "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": [".contentRight .itemBox"], "exclude_selectors": [".item2 span"]}}, "api": {"enabled": False, "reason": "静态HTML领导卡片有明确姓名和职务字段"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名和原始职务，不读取职责span。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".contentRight .itemBox")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in scope.select(":scope > a.item2") if scope else []:
        name_node = card.select_one(":scope > div > p")
        duty_node = card.select_one(":scope > div > div")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_cultural_relics_leader_cards_v1", "selector_summary": ".contentRight .itemBox > a.item2；p姓名、直接div职务"})
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
