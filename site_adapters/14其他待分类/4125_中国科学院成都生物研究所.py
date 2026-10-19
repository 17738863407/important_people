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
    "rule_id": "4125",
    "page_type": "leader_tables",
    "structure_group": "S4125",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.detail div.ue_table td",
    "risk_notes": "表格单元格中第一个强标签是姓名，下一段链接为同一人的职务与详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从当前领导表格按单元格顺序提取姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for cell in soup.select(rule["leader_region_selector"]):
        name_node = cell.select_one("p strong")
        paragraphs = cell.select("p")
        if name_node is None or len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", paragraphs[1].get_text(" ", strip=True))
        link = name_node.find_parent("a", href=True)
        if name and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(page_url, link["href"]) if link is not None else "",
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
