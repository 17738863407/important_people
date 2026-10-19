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


PAGE_RULE = {"rule_id": "4313", "page_type": "leader_photo_groups", "load_mode": "http", "parser": "custom", "risk": "人物卡片没有详情页链接，按标题后的相邻卡片组读取。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for heading in soup.select("h3.leadership-title"):
        duty = heading.get_text(" ", strip=True)
        cards = heading.find_next_sibling("div")
        if cards is None:
            cards = heading.parent.select_one(".leadership-one-box")
        for name_node in cards.select(".zxldxm") if cards else []:
            name = re.sub(r"[\s　]+", "", name_node.get_text(" ", strip=True))
            if name and duty:
                rows.append({"name": name, "duty": duty, "detail_url": ""})
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
