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
    "rule_id": "4120",
    "page_type": "leader_cards",
    "structure_group": "S4120",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div#box-2 dl.ld",
    "risk_notes": "主表旧入口已返回 404；现站点同栏目主页的 #box-2 提供实时领导卡片及详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """读取可复现的现站点领导卡片，保留主表入口作为输出依据链接。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    leader_page = "https://giec.cas.cn/yjsgk2016/"
    source_html = fetch_html_with_strategy(leader_page, strategy="requests", timeout=30).html
    soup = BeautifulSoup(source_html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        panel = card.select_one("dd")
        if panel is None:
            continue
        link = panel.select_one("a[href]")
        duty_node = panel.select_one("span")
        if link is None or duty_node is None:
            continue
        name = link.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True)
        if name and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(leader_page, link["href"]),
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
