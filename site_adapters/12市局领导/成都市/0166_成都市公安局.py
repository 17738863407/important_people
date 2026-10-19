from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0166",
    "page_type": "人物列表完整页",
    "structure_group": "cdgaj_ldcy_list_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "directory_detail",
    "collector": "chrome_cdp",
    "leader_region_selector": "div.html008 ul.list",
    "detail_strategy": {
        "required": True,
        "mode": "onclick_detail",
        "detail_name_selector": ".cont",
        "detail_duty_selector": "#myFont > p",
        "max_detail_links": 50,
    },
    "risk_flag": "入口页分页，人物详情链接位于 onclick，职务需从详情页强结构字段取得",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def extract_duty(detail_html: str) -> str:
    """提取详情页“职务：”标签后的相邻段落原文。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("#myFont")
    if content is None:
        return ""
    paragraphs = content.select(":scope > p")
    for index, paragraph in enumerate(paragraphs[:-1]):
        if paragraph.get_text(" ", strip=True).rstrip("：:") != "职务":
            continue
        return paragraphs[index + 1].get_text(" ", strip=True).removesuffix("。").strip()
    return ""


def extract_candidates(html: str, final_url: str) -> tuple[list[tuple[str, str]], int]:
    """按当前分页的 DOM 顺序提取姓名和 onclick 详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for item in soup.select("div.html008 ul.list > li.myflex"):
        name_node = item.select_one(":scope > .cont")
        onclick = str(item.get("onclick") or "")
        match = re.search(r"window\.open\(['\"]([^'\"]+)", onclick)
        if name_node is None or match is None:
            continue
        name = name_node.get_text(" ", strip=True)
        if name:
            candidates.append((name, urljoin(final_url, match.group(1))))

    page_numbers = [
        int(button.get("value"))
        for button in soup.select("div#page button.pageButton[value]")
        if str(button.get("value") or "").isdigit()
    ]
    return candidates, max(page_numbers, default=1)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态遍历全部分页，并从每个人物详情页取得原始职务。"""
    from crawler_core.fetcher import fetch_by_chrome_debug

    candidates, page_count = extract_candidates(html, final_url)
    for page_number in range(2, page_count + 1):
        page_url = urljoin(
            final_url,
            f"/gkml/ldcy/detail-list/column-index-{page_number}.shtml?page={page_number}",
        )
        page_result = fetch_by_chrome_debug(page_url)
        page_candidates, _ = extract_candidates(page_result.html, page_result.final_url)
        candidates.extend(page_candidates)

    rows: list[dict[str, str]] = []
    seen_detail_urls: set[str] = set()
    for order, (name, detail_url) in enumerate(candidates, start=1):
        if detail_url in seen_detail_urls:
            continue
        seen_detail_urls.add(detail_url)
        detail_result = fetch_by_chrome_debug(detail_url)
        duty = extract_duty(detail_result.html)
        rows.append(
            {
                "order": str(order),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_cdgaj_ldcy_list_detail_v1",
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
