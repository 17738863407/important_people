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
    "rule_id": "4402",
    "page_type": "government_leader_cards_by_title",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "政府领导区含空白隐藏卡片与无人物的秘书长分组；仅输出具有姓名链接的当前人物。",
    "confidence": "high",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按市长、副市长、秘书长分组顺序展开非空人物卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".szf-l .k1")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > .msz, :scope > .fsz"):
        duty_node = group.find("span", recursive=False)
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for link in group.select("ul li h3 a[href], ul li > a[href]:has(h3)"):
            name_node = link.select_one("h3 span")
            name = name_node.get_text(" ", strip=True) if name_node else link.get("title", "")
            name = re.sub(r"\s+", "", name)
            if name:
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
