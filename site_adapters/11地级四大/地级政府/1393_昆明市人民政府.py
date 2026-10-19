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
    "rule_id": "1393",
    "page_type": "人物卡片页",
    "structure_group": "kunming_government_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_government_leader_cards_v2",
    "leader_region_selector": ".right.leadership",
    "name_selector": ".leadership-top-data p.name, .leadership-item-data p.name",
    "duty_selector": ".leadership-top-data p.title b, .leadership-item-data p.title b",
    "detail_link_selector": ".leadership-top-data > a[href], .leadership-item-data > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "max_detail_links": 20,
    },
    "risk_flag": "姓名可能含零宽字符，市长、副市长和秘书长分属三个卡片容器但共享字段结构",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _clean_duty(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([、，；：）)])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市长、副市长、秘书长卡片的DOM顺序解析强结构字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for card in region.select(".leadership-top-data, .leadership-item-data"):
        link = card.select_one(":scope > a[href]")
        name_node = card.select_one("p.name")
        duty_node = card.select_one("p.title b")
        if link is None or name_node is None or duty_node is None:
            continue
        name = _clean_name(name_node.get_text(" ", strip=True))
        evidence = _clean_duty(duty_node.get_text(" ", strip=True))
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
