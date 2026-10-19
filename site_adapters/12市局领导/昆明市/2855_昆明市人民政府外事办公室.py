from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2855",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_foreign_affairs_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_foreign_affairs_grouped_cards_v1",
    "leader_region_selector": ".right.leadership",
    "name_selector": ".leadership-item-data a p",
    "duty_selector": ".leadership-item h3",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "detail_link_selector": ".leadership-item-data a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "names_have_typographic_letter_spacing",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".right.leadership",
            "groups": ".leadership-item",
            "group_duty": "h3",
            "cards": ".leadership-item-data a[href]",
            "name": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导分组和人物卡片直接包含职务、姓名及人物详情链接",
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
    """按职务分组与卡片DOM顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right.leadership")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for group in region.select(".leadership-item"):
        duty_node = group.select_one("h3")
        if duty_node is None:
            continue
        duty = normalize_space(duty_node.get_text(" ", strip=True))
        if not duty:
            continue
        for card in group.select(".leadership-item-data a[href]"):
            name_node = card.select_one("p")
            if name_node is None:
                continue
            name = re.sub(r"\s+", "", normalize_space(name_node.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url, str(card.get("href", "")).strip()),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".right.leadership；h3职务分组；人物卡片姓名；动态href",
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
