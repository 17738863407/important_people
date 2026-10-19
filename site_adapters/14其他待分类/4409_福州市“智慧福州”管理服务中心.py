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
    "rule_id": "4409",
    "page_type": "leader_dropdown_list",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "仅提取领导信息页面的更多领导列表，保留官网明确写出的兼任职务。",
    "confidence": "high",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按更多领导列表顺序提取姓名、完整职务和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".leader_name_list ul.dropdown_menu > li"):
        link = item.select_one("a[href]")
        name_node = item.select_one("a > span")
        duty_node = item.select_one("a > p")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if link and name and duty:
            detail_url = urljoin(final_url, link["href"])
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "" if detail_url == final_url else detail_url,
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
