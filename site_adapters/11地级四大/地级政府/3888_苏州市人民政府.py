from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3888",
    "page_type": "领导信息总页",
    "structure_group": "suzhou_government_breadcrumb_overview_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线DOM读取",
    "fetch_mode": "online",
    "extract_mode": "grouped_cards",
    "collector": "online_dom",
    "parser": "page_inline_suzhou_government_overview_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ldxx-leaders-item.ldxx-leaders-sz, .ldxx-leaders-item.ldxx-leaders-fsz",
    "name_selector": ".name a[href], .txt h4 a[href]",
    "duty_selector": ".title",
    "detail_link_selector": ".name a[href], .txt h4 a[href]",
    "overview_timeout_seconds": 45,
    "risk_flag": "仅抽取领导信息总页中市长、副市长直属区块，排除区县及部门负责人区块",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def find_overview_url(soup: BeautifulSoup, base_url: str) -> str:
    """从当前人物页面包屑中动态取得领导信息总页链接。"""
    base_host = urlparse(base_url).netloc.lower()
    for link in soup.select("a[href]"):
        if clean_text(link.get_text(" ", strip=True)) != "领导信息":
            continue
        candidate = urljoin(base_url, clean_text(link.get("href")))
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == base_host:
            return candidate
    raise RuntimeError("当前人物页面包屑中未找到同域领导信息总页链接")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """直接解析总页；兼容旧个人页回溯总页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = final_url or page_rule["url"]
    entry_soup = BeautifulSoup(html, "lxml")
    if entry_soup.select_one(page_rule["leader_region_selector"]):
        overview_soup = entry_soup
        overview_base = entry_url
    else:
        overview_url = find_overview_url(entry_soup, entry_url)
        overview_result = fetch_html_with_strategy(
            overview_url,
            strategy="playwright",
            timeout=int(page_rule["overview_timeout_seconds"]),
        )
        overview_soup = BeautifulSoup(overview_result.html, "lxml")
        overview_base = overview_result.final_url or overview_url

    rows: list[dict] = []
    seen_names: set[str] = set()
    for block in overview_soup.select(page_rule["leader_region_selector"]):
        title_node = block.select_one(":scope > .title") or block.select_one(".title")
        duty = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if duty not in {"市长", "副市长"}:
            continue
        for link in block.select(page_rule["detail_link_selector"]):
            name = clean_name(link.get_text(" ", strip=True))
            href = clean_text(link.get("href"))
            detail_url = urljoin(overview_base, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if name in seen_names or not detail_url:
                continue
            parsed = urlparse(detail_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": "面包屑领导信息链接；总页市长与副市长直属区块",
                }
            )

    if not rows:
        raise RuntimeError("领导信息总页未从市长、副市长区块提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
