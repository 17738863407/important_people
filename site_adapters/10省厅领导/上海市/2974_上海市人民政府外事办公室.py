from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2974",
    "page_type": "列表转人物详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leader-row",
    "item_selector": ".leader-row a.leader-item[href]",
    "risk_note": "详情正文在领导分工标题前可含多行并列职务，须完整保留并排除后续分工。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白，同时保留独立职务行之间的边界。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口卡片顺序在线读取详情，并截取领导分工标题前的职务文本。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for link in soup.select(page_rule["item_selector"]):
        name = re.sub(r"[\s\u3000\xa0]+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href", "").strip())
        if urlparse(detail_url).path.endswith("/ldxx/index.html"):
            continue

        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        content = detail_soup.select_one("#ivs_content")
        if content is None:
            continue
        content_text = clean_text(content.get_text(" ", strip=True))
        evidence = clean_text(re.split(r"领导分工\s*[:：]", content_text, maxsplit=1)[0])
        if not evidence or name not in re.sub(r"\s+", "", result.html):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": result.final_url,
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
