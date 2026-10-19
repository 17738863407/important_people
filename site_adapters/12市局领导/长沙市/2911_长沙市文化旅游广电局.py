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
    "rule_id": "2911",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_wlgd_directory_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_changsha_wlgd_directory_detail_v2",
    "leader_region_selector": ".xxgk-list > ul",
    "name_selector": "> li > a[href]",
    "duty_selector": "详情dl：第一dd h2=职务，第二dd=职务值",
    "detail_link_selector": "> li > a[href]",
    "detail_strategy": {"required": True, "mode": "directory_to_detail", "max_detail_links": 20},
    "risk_flag": "目录姓名含排版空格；详情页须用title核对姓名后读取职务强字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面文本中的空白字符。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """清理列表页姓名中间的排版空格。"""
    return clean_text(value).replace(" ", "").replace("\u3000", "")


def extract_duty(detail_html: str, expected_name: str) -> str:
    """核对详情页标题姓名并读取“职务”强字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    if not title.startswith(expected_name):
        return ""
    for group in soup.select("dl"):
        cells = group.find_all("dd", recursive=False)
        if len(cells) >= 2 and clean_name(cells[0].get_text(" ", strip=True)) == "职务":
            return clean_text(cells[1].get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口目录顺序在线抓取并核验人物详情职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    entry_url = str(page_rule.get("url") or "") or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(region.select(":scope > li > a[href]"), start=1):
        name = clean_name(link.get_text(" ", strip=True))
        href = clean_text(link.get("href", ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or entry_url, href)
        try:
            result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=source_order)
            duty = extract_duty(result.html, name)
        except Exception:
            continue
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization") or ""),
                "url": entry_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": (
                    "list=.xxgk-list > ul > li > a[href]；detail title核对姓名；"
                    "duty=dl中第一dd标题职务、第二dd值"
                ),
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
