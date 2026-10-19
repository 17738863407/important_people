from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2608",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#container",
    "item_selector": "#container a[href*='/jld/']",
    "risk_note": "同范围含局领导栏目导航，人物链接文本按姓名（职务）排列。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物链接顺序拆分括号外姓名、括号内职务和详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})（([^）]+)）", text)
        if not match:
            continue
        name = match.group(1)
        evidence = clean_text(match.group(2))
        candidate_url = urljoin(final_url, link.get("href", "").strip())
        detail_url = ""
        try:
            result = fetch_html_with_strategy(candidate_url, "raw_http")
            detail_text = re.sub(r"[\s\u3000\xa0]+", "", result.html)
            if name in detail_text:
                detail_url = result.final_url
        except Exception:
            detail_url = ""
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
