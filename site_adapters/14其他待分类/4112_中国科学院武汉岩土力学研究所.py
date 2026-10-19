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
    "rule_id": "4112",
    "page_type": "leader_cards",
    "structure_group": "S4112",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.gl_images_list div.image-box.layout_default",
    "risk_notes": "人物卡片的姓名、职务和个人介绍链接由同一可见链接节点提供。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从每张可见人物卡片的姓名链接中分离其后的职务文本。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one("span a b")
        link = card.select_one("span a[href]")
        if name_node is None or link is None:
            continue
        name = name_node.get_text(" ", strip=True)
        values = list(link.stripped_strings)
        duty = " ".join(values[1:]).strip() if values and values[0] == name else ""
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
