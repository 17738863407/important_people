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
    "rule_id": "1824",
    "page_type": "职务分组卡片页",
    "structure_group": "nanning_government_grouped_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "nanning_government_grouped_cards_v2",
    "leader_region_selector": ".gov-org-section",
    "name_selector": ".ldIMG > a[href] > p",
    "duty_selector": ".gov-title > span",
    "detail_link_selector": ".ldIMG > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "max_detail_links": 20,
    },
    "risk_flag": "姓名使用全角空格排版，职务由每个人物卡片所在分组标题继承",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按职务分组及组内卡片的DOM顺序解析人物。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for section in soup.select(page_rule["leader_region_selector"]):
        duty_node = section.select_one(".gov-title > span")
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not evidence:
            continue
        for link in section.select(".ldIMG > a[href]"):
            name_node = link.select_one(":scope > p")
            name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
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
