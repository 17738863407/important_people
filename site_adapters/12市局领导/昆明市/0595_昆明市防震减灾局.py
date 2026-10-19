from __future__ import annotations

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
    "rule_id": "0595",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_earthquake_leadership_card_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_earthquake_leadership_card_v1",
    "leader_region_selector": ".right.leadership .leadership-item",
    "name_selector": ".leadership-item-data a[href] p",
    "duty_selector": ".leadership-item > h3",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_group_links",
        "max_detail_links": 50,
    },
    "risk_flag": "同一职务分组可包含多人，必须保留组内DOM顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务分组和组内人物链接的DOM顺序解析卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in soup.select(page_rule["leader_region_selector"]):
        heading = group.select_one("h3")
        duty = clean_text(heading.get_text(" ", strip=True) if heading else "")
        if not duty:
            continue
        for link in group.select(".leadership-item-data a[href]"):
            name_node = link.select_one("p")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            key = (name, duty)
            if not name or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(base_url, link.get("href", "")),
                    "evidence": duty,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                }
            )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
