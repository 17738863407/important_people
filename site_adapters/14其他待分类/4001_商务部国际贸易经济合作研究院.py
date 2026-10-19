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
    "rule_id": "4001", "page_type": "研究院现任院领导卡片页", "structure_group": "caitec_current_leader_cards", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_caitec_current_leader_cards_v1",
    "leader_region_selector": ".organize-dean, .organize-leader", "name_selector": ".organize-dean h4, .organize-leader h4", "duty_selector": ".organize-dean p, .organize-leader p", "detail_link_selector": ".organize-dean a[href], .organize-leader a[href]",
    "content_scope": {"start_anchor": "院领导", "end_anchor": "历任院领导", "include_selectors": [".organize-dean"], "exclude_selectors": []}, "detail_strategy": {"required": False, "mode": "dynamic_card_link"},
    "risk_flag": "页面下方列有历任院领导；仅现任领导卡片结构可抽取。", "confidence": "high", "profile_reusable": False, "profile_judgement": "已核验当前院领导姓名、职务、详情链接均在独立卡片。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".organize-dean, .organize-leader", "name_selector": "h4", "duty_selector": "p", "detail_link_selector": "a[href]"}, "api": {"enabled": False, "reason": "当前HTML卡片完整呈现信息"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """读取现任院领导卡片，自动排除历任人员表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".organize-dean, .organize-leader li"):
        name_node, duty_node, link = card.select_one("h4"), card.select_one("p"), card.select_one("a[href]")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"]) if link else "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".organize-dean h4/p"})
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
