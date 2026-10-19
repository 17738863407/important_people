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
    "rule_id": "4107",
    "page_type": "leader_table",
    "structure_group": "S4107",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "table.w100.table",
    "risk_notes": "领导表格把多组“职务：姓名”写入同一单元格，须以真实姓名链接逐项对应。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """按表格文本顺序解析“职务：姓名”，并回取同名单独详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = next((item for item in soup.select("table") if item.select_one("a[href]")), None)
    if table is None:
        return []
    links = {
        item.get_text(" ", strip=True): urljoin(page_url, item["href"])
        for item in table.select("a[href]")
        if item.get_text(" ", strip=True)
    }
    rows: list[dict] = []
    for cell in table.select("td"):
        text = cell.get_text(" ", strip=True)
        for match in re.finditer(r"([^：:]+)[：:]\s*([\u4e00-\u9fff]{2,4})", text):
            duty = match.group(1).strip()
            name = match.group(2).strip()
            detail_url = links.get(name, "")
            if duty and detail_url:
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "evidence": duty,
                        "detail_url": detail_url,
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
