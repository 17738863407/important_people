from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0703",
    "page_type": "职务分组名单页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#ivs_content",
    "item_selector": "#ivs_content p",
    "risk_note": "正文以职务冒号姓名排列，职务中存在排版空格。",
    "confidence": "high",
}


def compact_text(value: str) -> str:
    """移除正文中的排版空白，不改变原始字符和标点。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文段落顺序拆分职务和冒号后的姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for paragraph in soup.select(page_rule["item_selector"]):
        text = compact_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,8})", text)
        if not match:
            continue

        evidence, name = match.groups()
        if not evidence:
            continue
        rows.append(
            {
                "name": name,
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
