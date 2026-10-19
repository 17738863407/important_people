from __future__ import annotations

import sys
from pathlib import Path
from posixpath import normpath
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4121",
    "page_type": "leader_cards",
    "structure_group": "S4121",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.personnel-style > ul.row > li",
    "risk_notes": "人物卡片的 h3、h4 为姓名、职务；仅保留不等于入口页的可验证详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从可见领导卡片提取姓名、职务和一一对应的详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one("h3")
        duty_node = card.select_one("h4")
        link = card.select_one("a[href]")
        if name_node is None or duty_node is None or link is None:
            continue
        name = name_node.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True)
        href = link.get("href", "").strip()
        detail_url = urljoin(page_url, href) if href else ""
        if detail_url:
            parts = urlsplit(detail_url)
            normalized_path = normpath(parts.path)
            if parts.path.endswith("/") and not normalized_path.endswith("/"):
                normalized_path += "/"
            detail_url = urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))
        if detail_url.rstrip("/") == page_url.rstrip("/"):
            detail_url = ""
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
