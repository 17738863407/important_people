from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2177",
    "page_type": "人物表格页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "table.work-ul",
    "item_selector": "table.work-ul",
    "risk_note": "表格文本按姓名、职位标签、简介重复排列；主职务只取职位标签字段。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按表格原始顺序解析姓名及职位标签字段。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(page_rule["leader_region_selector"])
    if table is None:
        return []
    text = clean_text(table.get_text(" ", strip=True))
    pattern = re.compile(r"(?P<name>[\u4e00-\u9fff·]{2,8})\s+职位[:：](?P<duty>.*?)\s+简介[:：]")
    rows: list[dict] = []

    for match in pattern.finditer(text):
        evidence = clean_text(match.group("duty")).strip("：:，,。.；; ")
        if not evidence:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "duty": "",
                "evidence": evidence,
                "detail_url": "",
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
