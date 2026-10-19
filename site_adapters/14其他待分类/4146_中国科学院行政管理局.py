from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4146", "page_type": "leader_cards", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "领导卡片提供姓名和“职务”字段，未提供详情页。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.box-s"):
        name_node, duty_node = card.select_one("div.box-title"), card.select_one("div.box-job")
        if name_node is None or duty_node is None:
            continue
        name = name_node.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True).removeprefix("职务：")
        if name and duty:
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("现任领导卡片未解析出姓名和职务")
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
