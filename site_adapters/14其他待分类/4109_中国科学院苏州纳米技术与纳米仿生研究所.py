from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4109",
    "page_type": "leader_cards",
    "structure_group": "S4109",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.personnel-style > ul > li",
    "risk_notes": "每张卡片以换行分隔职务和姓名，页面没有人物详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """保留卡片版面顺序，按首行职务、次行姓名解析。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        values = list(card.select_one("p").stripped_strings) if card.select_one("p") else []
        if len(values) < 2:
            continue
        duty, name = values[0].strip(), values[1].strip()
        if duty and name:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
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
