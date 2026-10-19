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
    "rule_id": "4133",
    "page_type": "leader_cards",
    "load_mode": "static",
    "fetch_mode": "online",
    "parser": "page_specific",
    "confidence": "high",
    "risk_notes": "领导卡片标题按“姓名 职务”展示，仅将标题后的职责说明排除。",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """解析领导卡片标题中的姓名、职务和可验证详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.ldteams li"):
        link = card.select_one("h4 a[href]")
        if link is None:
            continue
        parts = re.sub(r"\s+", " ", link.get_text(" ", strip=True).replace("\u3000", " ").replace("\u2002", " ")).split()
        if len(parts) < 2:
            continue
        if len(parts) >= 3 and all(re.fullmatch(r"[\u4e00-\u9fff]", part) for part in parts[:2]):
            name, duty = "".join(parts[:2]), "".join(parts[2:])
        else:
            name, duty = parts[0], "".join(parts[1:])
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(page_url, link["href"])})
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
