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
    "rule_id": "2250",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_market_supervision_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_market_supervision_leader_cards_v1",
    "leader_region_selector": "#to_leader_content",
    "name_selector": ".leader_name",
    "duty_selector": ".leader_identity",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "省局领导", "end_anchor": "相关链接", "include_selectors": ["#to_leader_content"], "exclude_selectors": [".tn_29_work"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "旧脚本硬编码全体人物；当前卡片有明确姓名、职务字段，详情链接仅存在于HTML注释中，不输出",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#to_leader_content", "name_selector": ".leader_name", "duty_selector": ".leader_identity", "detail_link_selector": "", "content_scope": {"start_anchor": "省局领导", "end_anchor": "相关链接", "include_selectors": ["#to_leader_content"], "exclude_selectors": [".tn_29_work"]}}, "api": {"enabled": False, "reason": "静态HTML领导卡片直接包含姓名和职务字段"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按省局领导卡片顺序动态提取姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#to_leader_content")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in scope.select(".organization_leader_right_list") if scope else []:
        name_node = card.select_one(".leader_name")
        duty_node = card.select_one(".leader_identity")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_market_supervision_leader_cards_v1", "selector_summary": "#to_leader_content领导卡片；.leader_name姓名、.leader_identity职务"})
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
