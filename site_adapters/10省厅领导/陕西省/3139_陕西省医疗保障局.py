from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3139",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leader-profile-page",
    "item_selector": ".leader-profile-page .top, .leader-profile-page .line",
    "risk_note": "人物卡片正文按页面顺序排列，卡片链接为独立人物介绍页。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变原始文字语义。"""
    return re.sub(r"\s+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物卡片顺序提取姓名、原始职务依据和真实详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        text = clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,8})", text)
        if not match:
            continue

        evidence = clean_text(match.group(1))
        name = clean_text(match.group(2))
        link = item.select_one("a[href]")
        detail_url = urljoin(final_url, link.get("href", "").strip()) if link else ""

        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": detail_url,
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
