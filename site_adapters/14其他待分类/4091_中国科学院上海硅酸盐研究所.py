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
    "rule_id": "4091", "page_type": "领导表格页", "structure_group": "sic_leader_table_card",
    "reuse_scope": "page_structure", "load_mode": "静态HTML直出", "extract_mode": "list_direct",
    "parser": "page_inline_sic_leader_table_card", "leader_region_selector": "table",
    "risk_flag": "姓名和职务位于同一表格单元格的相邻段落", "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐表格单元格提取姓名链接及紧随的职务段落。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for cell in soup.select("table td"):
        name_link = cell.select_one("p a[href]")
        paragraphs = cell.select("p")
        if name_link is None or len(paragraphs) < 2:
            continue
        name = name_link.get_text(" ", strip=True)
        duty = paragraphs[-1].get_text(" ", strip=True)
        if name and duty and any(word in duty for word in ("所长", "书记", "主任", "院长")):
            rows.append({"name": name, "duty": duty, "evidence": duty,
                         "detail_url": urljoin(final_url, name_link["href"])})
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
