from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4398",
    "page_type": "four_leadership_sidebar_table",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "同页侧栏包含四套班子；仅从标题为市政府的分组表格继承职务。",
    "confidence": "high",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", "", value).rstrip("：:")


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按市政府表格的行序和行内链接顺序提取人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_link = soup.select_one('#Left_Nav > li > a[title="市政府"]')
    group = title_link.find_parent("li") if title_link else None
    if group is None:
        return []
    rows: list[dict[str, str]] = []
    for table_row in group.select("dl table tr"):
        duty_node = table_row.select_one("td span")
        duty = _clean(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for link in table_row.select("td a[href]"):
            name = _clean(link.get_text(" ", strip=True))
            if name:
                rows.append({"name": name, "duty": duty, "detail_url": link["href"]})
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
