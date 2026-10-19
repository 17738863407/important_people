from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3266",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_garden_leadership_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_garden_leadership_cards_v1",
    "leader_region_selector": ".leadership-item-data",
    "name_selector": ".name",
    "duty_selector": ".title",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "detail_link_selector": ".leadership-item-data a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "card_fields_are_explicit_and_must_not_be_semantically_prefixed",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "cards": ".leadership-item-data a[href]",
            "name": ".name",
            "duty": ".title",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物卡片直接包含明确姓名、职务字段和独立人物链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不添加机构前缀。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片DOM顺序读取明确姓名、职务字段及动态链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select(".leadership-item-data a[href]"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".title")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", normalize_space(name_node.get_text(" ", strip=True)))
        duty = normalize_space(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(card.get("href", "")).strip()),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "人物卡片；.name；.title；动态href",
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
