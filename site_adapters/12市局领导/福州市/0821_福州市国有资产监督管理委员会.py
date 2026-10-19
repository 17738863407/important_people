from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0821",
    "page_type": "列表转人物详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leader_xx, .leader_xm",
    "risk_note": "其他领导列表仅含姓名，职务须由当前详情页标题动态取得；末项领导活动没有人物标题。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2003]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """移除姓名排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def http_fetch_url(value: str) -> str:
    """该站HTTP详情响应稳定，采集时使用同一资源的HTTP地址。"""
    parts = urlsplit(value)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, ""))


def leader_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    """按主领导和其他领导的页面顺序生成详情候选。"""
    pairs: list[tuple[str, str]] = []
    main_name = soup.select_one(".leader_xx h6 b")
    main_link = soup.select_one(".leader_xx a[href]")
    if main_name and main_link:
        pairs.append((clean_name(main_name.get_text(" ", strip=True)), urljoin(base_url, main_link.get("href", ""))))
    for link in soup.select(".leader_xm a[title][href]"):
        pairs.append((clean_name(link.get("title", "")), urljoin(base_url, link.get("href", ""))))
    return pairs


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """在线读取每个详情页标题中的姓名和完整职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for name, detail_url in leader_links(soup, final_url):
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        result = fetch_html_with_strategy(http_fetch_url(detail_url), "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        heading_node = detail_soup.select_one("h3.fs_h8")
        heading = clean_text(heading_node.get_text(" ", strip=True) if heading_node else "")
        if not heading.startswith(name):
            continue
        evidence = clean_text(heading[len(name) :])
        if not evidence:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": "", "evidence": evidence, "detail_url": detail_url})
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
