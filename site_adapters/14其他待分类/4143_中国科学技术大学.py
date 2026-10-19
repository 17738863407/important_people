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


PAGE_RULE = {"rule_id": "4143", "page_type": "leader_table", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "现任领导表格以同一行的 strong 职务和姓名链接构成记录。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for row in soup.select("tr"):
        duty_node, link = row.select_one("strong"), row.select_one("a[title][href]")
        if duty_node is None or link is None:
            continue
        name, duty = "".join(link.get_text(" ", strip=True).split()), duty_node.get_text(" ", strip=True)
        if name and duty:
            detail_url = urljoin(page_url, link["href"])
            marker = (name, duty, detail_url)
            if marker not in seen:
                seen.add(marker)
                rows.append({"name": name, "duty": duty, "detail_url": detail_url})
    if not rows:
        raise RuntimeError("现任领导表格未解析出姓名和职务")
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
