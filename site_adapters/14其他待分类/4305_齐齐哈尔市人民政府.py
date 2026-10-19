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


PAGE_RULE = {"rule_id": "4305", "page_type": "multi_group_leader_list", "load_mode": "http", "parser": "custom", "risk": "同一组件顺序含市委、人大、政府、政协，依据市政府详情栏目路径筛选。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".szf .lingdao .item"):
        link = item.select_one("a[href]")
        label = item.select_one("label")
        if not link or not label or not any(part in link["href"] for part in ("/c100055/", "/c100058/", "/c103804/")):
            continue
        duty = label.get_text(" ", strip=True)
        for person in item.select("li a[href]"):
            name = re.sub(r"[\s　]+", "", person.get_text(" ", strip=True))
            if name:
                rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, person["href"])})
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
