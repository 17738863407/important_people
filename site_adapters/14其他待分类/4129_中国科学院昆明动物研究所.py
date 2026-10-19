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
    "rule_id": "4129",
    "page_type": "leader_cards",
    "load_mode": "static",
    "fetch_mode": "online",
    "parser": "page_specific",
    "confidence": "high",
    "risk_notes": "同页同时展示现任和历任领导，仅采集“现任领导”标题后的首组卡片。",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """解析“现任领导”分区内按“职务--姓名”展示的人物卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.swiper-no-swiping")
    heading = content.find(string=lambda value: value and value.strip() == "现任领导") if content else None
    if heading is None:
        raise RuntimeError("未找到“现任领导”分区标题")
    title_box = heading.find_parent("div")
    title_row = title_box.find_parent("div") if title_box else None
    card_box = title_row.find_next_sibling("div") if title_row else None
    cards = card_box.select("div.kiznews") if card_box else []
    rows: list[dict] = []
    for card in cards:
        link = card.select_one("p a[href]")
        if link is None:
            continue
        text = " ".join(link.stripped_strings)
        match = re.fullmatch(r"\s*(.+?)\s*-{2,}\s*([\u4e00-\u9fff]{2,4})\s*", text)
        if match is None:
            continue
        duty, name = match.groups()
        rows.append(
            {
                "name": name,
                "duty": duty.strip(),
                "detail_url": urljoin(page_url, link["href"]),
            }
        )
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
