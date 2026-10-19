from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0346",
    "page_type": "人物列表完整页",
    "load_mode": "脚本跳转后HTML直出",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".ulli",
    "item_selector": ".ulli li a[href]",
    "risk_note": "入口通过页面脚本跳转至index.html，online采集需保留跳转处理。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白，保留职务中的原始标点。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导简介列表顺序拆分开头姓名和后续职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})\s+(.+)", text)
        if not match:
            continue

        name = clean_text(match.group(1))
        evidence = clean_text(match.group(2))
        detail_url = urljoin(final_url, link.get("href", "").strip())
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
