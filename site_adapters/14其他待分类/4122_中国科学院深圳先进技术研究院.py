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
    "rule_id": "4122",
    "page_type": "leader_cards",
    "structure_group": "S4122",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.leader > ul.row > li",
    "risk_notes": "领导卡片的 h2、h3 和链接为姓名、现职、个人详情强结构。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从当前领导卡片中提取姓名、现职和个人详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one("h2")
        duty_node = card.select_one("h3")
        link = card.select_one("a.leader-item[href]")
        if name_node is None or duty_node is None or link is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = duty_node.get_text(" ", strip=True)
        if name and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(page_url, link["href"]),
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
