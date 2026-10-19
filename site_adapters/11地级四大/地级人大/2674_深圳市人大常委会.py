from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2674",
    "page_type": "人物卡片页",
    "structure_group": "shenzhen_people_congress_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "shenzhen_people_congress_leader_cards_v2",
    "leader_region_selector": "body.home > div.container.mx-auto.mt-10",
    "name_selector": ".flex.py-3.pl-3 p.font-medium",
    "duty_selector": ".flex.py-3.pl-3 h2",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "页面使用工具类样式，解析同时要求姓名和职务位于同一领导卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导班子卡片DOM顺序抽取姓名和卡片原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for card in region.select(".flex.py-3.pl-3"):
        name_node = card.select_one("p.font-medium")
        duty_node = card.select_one("h2")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not evidence:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
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
