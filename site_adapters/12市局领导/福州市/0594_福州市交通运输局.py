from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0594",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "leader_region_selector": "[role='viewlist'][des='领导信息']",
    "main_link_selector": ".leader_xx a[href]",
    "other_link_selector": ".leader_xm a[href]",
    "detail_title_selector": (
        "[role='viewlist'][des='领导信息'] .leader_content h3.fs_h8"
    ),
    "detail_timeout_seconds": 30,
    "risk_flag": "入口页仅完整展示主要领导职务，其他领导需按当前链接进入详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空格，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def split_detail_title(title: str, expected_name: str) -> tuple[str, str]:
    """依据列表页姓名，从详情页“职务 姓名”标题中分离原始职务。"""
    compact_title = clean_text(title)
    compact_name = clean_name(expected_name)
    title_without_spaces = re.sub(r"\s+", "", compact_title)
    if not title_without_spaces.endswith(compact_name):
        return "", ""
    duty_length = len(title_without_spaces) - len(compact_name)
    return compact_name, title_without_spaces[:duty_length].strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口页人物链接顺序读取各详情页的明确职务标题。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导信息区域")

    links = []
    seen_urls: set[str] = set()
    for selector in (page_rule["main_link_selector"], page_rule["other_link_selector"]):
        for link in region.select(selector):
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not detail_url or detail_url in seen_urls:
                continue
            raw_name = link.get("title") or link.get_text(" ", strip=True)
            name = clean_name(raw_name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
                continue
            seen_urls.add(detail_url)
            links.append((name, detail_url))

    rows: list[dict] = []
    for name, detail_url in links:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        title_node = detail_soup.select_one(page_rule["detail_title_selector"])
        detail_name, duty = split_detail_title(
            title_node.get_text(" ", strip=True) if title_node else "",
            name,
        )
        if detail_name != name or not duty:
            raise RuntimeError(f"详情页职务标题无法与姓名对应：{name} / {detail_url}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_fuzhou_transport_detail_title_v1",
                "selector_summary": (
                    "region=[role='viewlist'][des='领导信息']；"
                    "links=.leader_xx a[href],.leader_xm a[href]；"
                    "detail_title=.leader_content h3.fs_h8"
                ),
            }
        )
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
