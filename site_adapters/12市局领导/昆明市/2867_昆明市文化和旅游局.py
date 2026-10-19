from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2867",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_culture_tourism_leadership_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_culture_tourism_leadership_cards_v1",
    "leader_region_selector": ".leadership-item",
    "name_selector": ".leadership-item-data a末尾姓名",
    "duty_selector": ".leadership-item-data a中姓名前职务",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "detail_link_selector": ".leadership-item-data a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "page_contains_duplicate_metadata_list_and_leadership_cards",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "groups": ".leadership-item",
            "cards": ".leadership-item-data a[href]",
            "card_title": "full link text",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导卡片直接包含职务姓名标题和独立人物链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不改写职务分隔。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导分组和卡片DOM顺序动态提取。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select(".leadership-item .leadership-item-data a[href]"):
        title = normalize_space(card.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,4})", title)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        if not re.search(r"党组|局长|组长", duty) or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(card.get("href", "")).strip()),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导分组人物卡片；完整职务姓名标题；动态href",
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
