from __future__ import annotations

import sys
import re
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
    "rule_id": "2850",
    "page_type": "人物目录详情页",
    "structure_group": "beijing_foreign_affairs_sidebar_details",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_beijing_foreign_affairs_details_v1",
    "leader_region_selector": ".list.jgzn .item",
    "name_selector": ".sub-list .sub-item a[title][href]",
    "duty_selector": ".TRS_UEDITOR",
    "detail_link_selector": ".sub-list .sub-item a[title][href]",
    "detail_strategy": {"required": True, "mode": "sidebar_to_detail"},
    "risk_flag": "页面模板含浏览器版本提示语但原始HTML完整；只读取外办领导侧栏及详情唯一职务行",
    "confidence": "high",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\u3000", " ")).strip()


def extract_duty(detail_html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(".TRS_UEDITOR")
    evidence = clean_text(node.get_text(" ", strip=True) if node else "")
    match = re.fullmatch(rf"{re.escape(name)}[，,](?P<duty>.+)", evidence)
    return (match.group("duty"), evidence) if match else ("", "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    import requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = urljoin(final_url, str(page_rule.get("url") or "").strip())
    leader_item = None
    for item in soup.select(".list.jgzn .item"):
        heading = item.select_one(":scope > p.top")
        if clean_text(heading.get_text(" ", strip=True) if heading else "") == "外办领导":
            leader_item = item
            break
    if leader_item is None:
        return []

    for link in leader_item.select(".sub-list .sub-item a[title][href]"):
        name = clean_text(link.get("title") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        if name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url == final_url:
            detail_html = html
        else:
            response = requests.get(
                detail_url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
        duty, evidence = extract_duty(detail_html, name)
        if not duty or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "" if detail_url == source_url else detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_beijing_foreign_affairs_details_v1",
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
