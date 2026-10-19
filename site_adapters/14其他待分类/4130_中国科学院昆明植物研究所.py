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
    "rule_id": "4130",
    "page_type": "leader_list",
    "load_mode": "static",
    "fetch_mode": "online",
    "parser": "page_specific",
    "confidence": "high",
    "risk_notes": "只采集正文现任领导列表，链接文本以末尾空白分隔职务和姓名。",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """按列表项链接文本的最后一个空白片段取得姓名。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("div.textlist4")
    rows: list[dict] = []
    for link in box.select("li > a[href]") if box else []:
        parts = link.get_text(" ", strip=True).split()
        if len(parts) < 2:
            continue
        rows.append(
            {
                "name": parts[-1],
                "duty": "".join(parts[:-1]),
                "detail_url": urljoin(page_url, link["href"]),
            }
        )
    if not rows:
        raise RuntimeError("现任领导列表未解析出姓名和职务")
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
