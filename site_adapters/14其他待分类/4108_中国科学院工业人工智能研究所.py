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
    "rule_id": "4108",
    "page_type": "leader_cards",
    "structure_group": "S4108",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "css_fields",
    "parser": "V001",
    "leader_region_selector": "div.column-box.recai-item > div[class*='col-']",
    "name_selector": ".people-name",
    "duty_selector": ".people-zc",
    "risk_notes": "人物卡片未提供可验证的实际详情链接；HTML注释中的旧链接不参与抽取。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从可见人物卡片提取姓名和现职，保留空详情页链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one(rule["name_selector"])
        duty_node = card.select_one(rule["duty_selector"])
        if name_node is None or duty_node is None:
            continue
        name = name_node.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True)
        if name and duty:
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
