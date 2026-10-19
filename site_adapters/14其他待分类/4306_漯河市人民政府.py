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


PAGE_RULE = {"rule_id": "4306", "page_type": "leader_list", "load_mode": "http", "parser": "custom", "risk": "领导之窗之外还有会议列表，限定市政府领导人物区。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".leaderbox > .bd")
    if body is None:
        return []
    rows: list[dict[str, str]] = []
    current_duty = ""
    for child in body.find_all(recursive=False):
        if child.name == "p":
            current_duty = child.get_text(" ", strip=True).rstrip(":： ")
            continue
        items = child.select("li") if "mayor" in (child.get("class") or []) else [child]
        for item in items:
            title = item.select_one("h3.title")
            link = title.select_one("a[href]") if title else None
            duty = title.select_one(".job") if title else None
            raw_duty = duty.get_text(" ", strip=True) if duty else ""
            if link and (raw_duty or current_duty):
                rows.append({"name": re.sub(r"[\s　]+", "", link.get_text(" ", strip=True)), "duty": raw_duty or current_duty, "detail_url": urljoin(final_url, link["href"])})
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
