from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2740",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div#tab1-b ul.Bureau_leader",
    "item_selector": "div#tab1-b ul.Bureau_leader li a[href]",
    "risk_note": "链接title为姓名，可见文本以冒号分隔姓名和职务。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清理姓名或职务字段中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导目录链接顺序提取姓名、职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for link in soup.select(page_rule["item_selector"]):
        name = clean_text(link.get("title", ""))
        text = clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"[:：]", text, maxsplit=1)
        evidence = parts[1] if len(parts) == 2 else ""
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not evidence
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, link.get("href", "").strip()),
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
