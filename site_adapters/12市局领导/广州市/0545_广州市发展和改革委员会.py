from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0545",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "leader_region_selector": ".sideMenu",
    "detail_link_selector": "li a[href]",
    "detail_name_selector": ".ldname",
    "detail_duty_selector": ".ldzw",
    "detail_timeout_seconds": 30,
    "risk_flag": "入口页侧栏给出人物顺序，各详情页提供姓名和职务；禁止读取旧快照",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空白，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按侧栏顺序在线抓取人物详情页并提取明确姓名、职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导之窗侧栏")

    base_url = final_url or page_rule["url"]
    detail_urls: list[str] = []
    for link in region.select(page_rule["detail_link_selector"]):
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if "/zfxxgk/ldzc/" not in detail_url or detail_url in detail_urls:
            continue
        detail_urls.append(detail_url)

    rows: list[dict] = []
    seen_names: set[str] = set()
    for detail_url in detail_urls:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        name_node = detail_soup.select_one(page_rule["detail_name_selector"])
        duty_node = detail_soup.select_one(page_rule["detail_duty_selector"])
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            raise RuntimeError(f"详情页缺少可靠姓名或职务：{detail_url}")
        if name in seen_names:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_guangzhou_ndrc_online_details_v2",
                "selector_summary": "entry=.sideMenu li a[href]；detail_name=.ldname；detail_duty=.ldzw",
            }
        )

    if not rows:
        raise RuntimeError("领导详情页未提取到有效人物")
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
