from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3229",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "h4局领导后的表格链接及各详情页div.list-contant.resume",
    "item_selector": "a[href*='/jczc/']",
    "risk_note": "旧合并页已失效；从同站局长之窗动态发现人物详情链接，按局领导表格顺序逐页读取h5姓名与h6现职。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按“局领导”表格顺序逐页提取姓名、现职和真实人物详情链接。"""
    del html, final_url
    from crawler_core.fetcher import fetch_html_with_strategy

    directory_result = fetch_html_with_strategy(derive_directory_url(str(page_rule["url"])), strategy="requests")
    directory_soup = BeautifulSoup(directory_result.html, "html.parser")
    detail_urls: list[str] = []
    seen_urls: set[str] = set()
    for link in directory_soup.select("a[href*='/jczc/'][title]"):
        name = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(directory_result.final_url, href)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not href.endswith(".html") or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_urls.append(detail_url)

    rows: list[dict] = []
    seen_names: set[str] = set()
    for detail_url in detail_urls:
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        region = detail_soup.select_one("div.list-contant.resume")
        name_node = region.select_one("h5") if region else None
        duty_node = region.select_one("h6") if region else None
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": detail_result.final_url,
            }
        )

    return rows


def derive_directory_url(source_url: str) -> str:
    """根据权威来源域名定位同站“局长之窗”入口，不固化人物详情页。"""
    parts = urlsplit(source_url)
    if not parts.scheme or not parts.netloc:
        raise RuntimeError("规则入口缺少有效站点信息")
    return urlunsplit((parts.scheme, parts.netloc, "/jczc/index.html", "", ""))


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
