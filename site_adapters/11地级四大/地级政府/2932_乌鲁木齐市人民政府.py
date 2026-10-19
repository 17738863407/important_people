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
    "rule_id": "2932",
    "page_type": "人物卡片页",
    "structure_group": "wulumuqi_government_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_government_leader_cards_v2",
    "leader_region_selector": ".zfxxgk_zfld_box",
    "name_selector": "> ul > li p span a[href]",
    "duty_selector": "> ul > li p b",
    "detail_link_selector": "> ul > li p span a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_card_links",
        "max_detail_links": 20,
    },
    "risk_flag": "姓名可能包含中间点，卡片另有同一人物图片链接；只取文本字段链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _clean_duty(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片DOM顺序解析姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for card in region.select(":scope > ul > li"):
        name_node = card.select_one("p span a[href]")
        duty_node = card.select_one("p b")
        name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_duty(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not evidence:
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
                detail_url=urljoin(entry_url, name_node["href"]),
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
