from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2011",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul.leaderlist",
    "row_selector": "ul.leaderlist > li",
    "name_selector": "a[href] > p",
    "duty_selector": "详情页顶部职务字段或本人正文首段当前职务句段",
    "detail_link_selector": "a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表页仅含姓名和详情链接，职务需逐详情动态提取；首位详情无独立顶部职务字段，只能在其本人正文首段分号后的明确当前职务句段内提取。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """读取单个人物详情页的标题姓名和明确当前职务。"""
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(".title h1")
    name = normalize_text(title_node.get_text(" ", strip=True) if title_node is not None else "").replace(" ", "")
    if name != expected_name or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
        return None

    duty = ""
    marker = soup.select_one('meta[name="ContentStart"]')
    if marker is not None:
        sibling = marker.find_next_sibling("span")
        if sibling is not None:
            duty = normalize_text(sibling.get_text(" ", strip=True))

    if not duty:
        first_paragraph = soup.select_one(".view p")
        paragraph = normalize_text(first_paragraph.get_text(" ", strip=True) if first_paragraph is not None else "")
        match = re.search(r"；([^。]+(?:局长|副局长|药品安全总监))。", paragraph)
        if match is not None:
            duty = normalize_text(match.group(1))

    if not duty:
        return None
    return {"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表页人物顺序逐详情在线提取当前职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select("ul.leaderlist > li"):
        link = card.select_one("a[href]")
        name_node = card.select_one("a[href] > p")
        if link is None or name_node is None:
            continue
        name = normalize_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        href = normalize_text(link.get("href", ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not href:
            continue

        detail_url = urljoin(final_url, href)
        try:
            detail_html = fetch_html_with_strategy(detail_url, "raw_http").html
            row = parse_detail(detail_html, name, detail_url)
        except Exception:
            continue
        if row is not None:
            rows.append(row)

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
