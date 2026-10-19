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
    "rule_id": "4397",
    "page_type": "four_leadership_groups",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "同页包含市委、人大、政府、政协四组领导；仅提取包含市长详情路径的市政府分组。",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", "", value).rstrip("：:")


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """在四组领导中定位市政府分组并按网页顺序展开职务标题。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    government = None
    for group in soup.select("#ldzc .affairs_information > div"):
        if group.select_one('a[href*="/ldzc/szfld/sz/"]'):
            government = group
            break
    if government is None:
        return []

    rows: list[dict[str, str]] = []
    primary = government.select_one(".information_content")
    if primary:
        duty_node = primary.select_one(".secretary")
        link = primary.select_one("a[href]")
        if duty_node and link:
            name = _clean_text(link.get_text(" ", strip=True))
            duty = _clean_text(duty_node.get_text(" ", strip=True))
            if name and duty:
                rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"])})

    for section in government.select(".information_other > div"):
        duty_node = section.select_one(".information_title")
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for link in section.select(".information_right a"):
            name = _clean_text(link.get_text(" ", strip=True))
            if name:
                href = link.get("href", "")
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": urljoin(final_url, href) if href else "",
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
