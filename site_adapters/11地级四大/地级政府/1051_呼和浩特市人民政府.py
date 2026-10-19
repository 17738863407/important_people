from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1051",
    "page_type": "人物列表完整页",
    "structure_group": "huhhot_government_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "huhhot_government_leader_cards_v2",
    "leader_region_selector": ".ldzc_block1",
    "name_selector": ".ldzc_block1_left .block1 p a[title], .ldzc_block1_right li a[title] > span",
    "duty_selector": ".ldzc_block1_left .block1 p > span, .ldzc_block1_right li a[title] > p",
    "detail_link_selector": ".ldzc_block1_left .block1 > a[title], .ldzc_block1_right li > a[title]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "max_detail_links": 20,
    },
    "risk_flag": "市长使用独立主卡片，其余领导使用右侧列表卡片，简介和领导活动链接不属于人物入口",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市长主卡片及右侧领导卡片的DOM顺序解析人物。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    cards = []
    mayor_card = region.select_one(".ldzc_block1_left .block1")
    if mayor_card is not None:
        cards.append((mayor_card, ".block1 > a[title]", "p a[title]", "p > span"))
    cards.extend(
        (item, "a[title]", "a[title] > span", "a[title] > p")
        for item in region.select(".ldzc_block1_right li")
    )

    records: list[object] = []
    seen: set[str] = set()
    for card, link_selector, name_selector, duty_selector in cards:
        link = card.select_one(link_selector)
        name_node = card.select_one(name_selector)
        duty_node = card.select_one(duty_selector)
        if link is None or name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            continue
        if name in seen:
            continue
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=urljoin(entry_url, link["href"]),
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
