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
    "rule_id": "2881",
    "page_type": "人物卡片页",
    "structure_group": "wuhan_people_congress_leader_cards_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_people_congress_leader_cards_v3",
    "leader_region_selector": ".rq-pics-page",
    "name_selector": ".RQPP-list > li p > b",
    "duty_selector": ".RQPP-list > li > p > p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "姓名位于卡片外层p的b子节点，职务已改为同一外层p中的内层p；页面另有隐藏空卡片，必须跳过。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片DOM顺序提取b姓名和p直接职务文本。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for item in region.select(".RQPP-list > li"):
        paragraph = item.find("p", recursive=False)
        name_node = paragraph.find("b", recursive=False) if paragraph else None
        duty_node = paragraph.find("p", recursive=False) if paragraph else None
        if paragraph is None or name_node is None or duty_node is None:
            continue
        name = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            name_node.get_text(" ", strip=True),
        )
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
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
