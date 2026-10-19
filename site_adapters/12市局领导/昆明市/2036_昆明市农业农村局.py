from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2036",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_agriculture_leadership_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_agriculture_leadership_cards_v1",
    "leader_region_selector": ".right.leadership .leadership-inner",
    "name_selector": "a .name",
    "duty_selector": "a ._1st-duty p:not(.name), a p.title",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "detail_link_selector": "a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "first_card_and_rest_cards_use_different_duty_containers",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "cards": ".right.leadership .leadership-inner a[href]",
            "name": ".name",
            "first_duty_lines": "._1st-duty p:not(.name)",
            "rest_duty_lines": "p.title",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导卡片直接包含姓名、多行职务和人物详情链接",
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
    """按卡片DOM顺序动态提取姓名、多行职务及人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select(".right.leadership .leadership-inner a[href]"):
        name_node = card.select_one(".name")
        if name_node is None:
            continue
        name = normalize_space(name_node.get_text(" ", strip=True))
        duty_nodes = card.select("._1st-duty p:not(.name), p.title")
        duty_parts = [normalize_space(node.get_text(" ", strip=True)) for node in duty_nodes]
        duty = " ".join(part for part in duty_parts if part)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, str(card.get("href", "")).strip())
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".right.leadership人物卡片；.name；全部职务行；卡片href",
            }
        )
    return rows


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
