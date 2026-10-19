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
    "rule_id": "4405",
    "page_type": "government_leader_full_list",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "人物块同时包含简介与分工；仅以块首姓名--职务标题为现职证据，排除职责正文。",
    "confidence": "high",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按列表页人物块顺序解析姓名--职务标题及详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".list-page")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for link in region.select(".ldtxt > p a[href]"):
        title = link.get_text(" ", strip=True)
        match = re.fullmatch(r"\s*(.+?)\s*--\s*(.+?)\s*", title)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = match.group(2).strip()
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link["href"]),
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
