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
    "rule_id": "4119",
    "page_type": "leader_cards",
    "structure_group": "S4119",
    "reuse_level": "site_specific",
    "load_mode": "raw_html",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "ul#content li.box-w",
    "risk_notes": "页面脚本会跳转至机构首页；原始响应的 #content 才含当前领导卡片。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从原始响应的当前领导卡片中提取姓名、职务和有效详情链接。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    raw_html = fetch_html_with_strategy(page_url, strategy="raw_http", timeout=30).html
    soup = BeautifulSoup(raw_html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one(".box-title span")
        duty_node = card.select_one(".box-txt-01")
        link = card.select_one("a.box-s[href]")
        if name_node is None or duty_node is None or link is None:
            continue
        name = name_node.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True)
        href = link.get("href", "").strip()
        detail_url = urljoin(page_url, href) if href and href != "#" else ""
        if name and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url})
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
