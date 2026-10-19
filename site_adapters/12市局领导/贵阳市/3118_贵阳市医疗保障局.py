from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3118",
    "page_type": "人物目录详情页",
    "structure_group": "领导目录链接与详情职务字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "a[href*='jgld_5978808'][href$='.html'][title]",
    "name_selector": "a[title]",
    "duty_selector": ".drzz span",
    "detail_link_selector": "a[href*='jgld_5978808'][href$='.html'][title]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "页面脚本会跳转站内搜索，入口及详情使用raw_http保留权威原始HTML",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[href*='jgld_5978808'][href$='.html'][title]"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url in seen_urls:
            continue
        name = clean_text(str(link.get("title") or "")).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
            continue
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(detail.html, "html.parser")
        detail_title = clean_text(detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
        duty_node = detail_soup.select_one(".drzz span")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if name not in detail_title or not duty:
            raise ValueError(f"详情页标题或职务字段校验失败：{detail.final_url}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail.final_url,
                "selector_summary": "机构领导目录title姓名及详情.drzz span职务字段",
            }
        )
        seen_urls.add(detail_url)
    if not rows:
        raise ValueError("机构领导目录未发现可验证的人物详情记录")
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
