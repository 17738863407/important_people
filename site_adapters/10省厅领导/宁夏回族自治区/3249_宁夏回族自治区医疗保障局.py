from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3249",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".news-content-list",
    "row_selector": ".news-content-list li",
    "name_selector": "li > a[href]直属文本",
    "duty_selector": "详情页.content h2",
    "detail_link_selector": "li > a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表链接同时含姓名和i日期，姓名只取a直属文本；职务从详情页独立h2字段提取，禁止读取本地详情快照。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """读取人物详情页标题姓名与独立h2职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".content .title")
    duty_node = soup.select_one(".content h2")
    name = normalize_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
    duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
    if name != expected_name or not duty:
        return None
    return {"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表DOM顺序动态抓取详情并提取职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".news-content-list li"):
        link = item.select_one("a[href]")
        if link is None:
            continue
        direct_text = " ".join(str(node) for node in link.find_all(string=True, recursive=False))
        name = normalize_text(direct_text).replace(" ", "")
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
