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


PAGE_RULE = {"rule_id": "4307", "page_type": "leader_cards", "load_mode": "http", "parser": "custom", "risk": "页面领导信息与政府文件同页，限定市政府领导卡片。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for group in soup.select(".m-mainleftleader .m-leaderbox"):
        duty = re.sub(r"[\s　]+", "", group.select_one(".u-leaderJob").get_text(" ", strip=True)) if group.select_one(".u-leaderJob") else ""
        for link in group.select(".m-leaderName a[href]"):
            name = re.sub(r"[\s　]+", "", link.get_text(" ", strip=True))
            if name and duty:
                rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"])})
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
