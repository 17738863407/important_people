from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4161", "page_type": "leader_table", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "人员表每行按姓名、职务成对排列，图片链接不是个人详情页。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for row in soup.select("tbody.row-striping tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 4 or any(cell.find("img") is not None for cell in cells):
            continue
        values = [cell.get_text(" ", strip=True) for cell in cells]
        for name, duty in ((values[0], values[1]), (values[2], values[3])):
            if name and duty:
                duty = "；".join(
                    part.strip()
                    for part in duty.replace("，", ",").split(",")
                    if part.strip()
                )
                rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("行政管理人员表未解析出姓名和职务")
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
