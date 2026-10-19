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
    "rule_id": "3254",
    "page_type": "人物目录详情页",
    "structure_group": "guizhou_healthcare_profile_details",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_guizhou_healthcare_profile_details_v1",
    "leader_region_selector": "#Left_Nav",
    "name_selector": "#Left_Nav > li > a[title][href]",
    "duty_selector": ".profile_right table",
    "detail_link_selector": "#Left_Nav > li > a[title][href]",
    "detail_strategy": {"required": True, "mode": "list_to_profile_table"},
    "risk_flag": "入口正文仅展示首人资料；必须按左侧目录顺序逐一读取详情表格",
    "confidence": "high",
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").replace("\xa0", " ").replace("\u3000", " "))


def _extract_profile(detail_html: str) -> tuple[str, str]:
    """从单个人物详情页的强结构表格读取姓名和原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select(".profile_right table tr"):
        cells = row.select(":scope > td")
        if len(cells) != 2:
            continue
        label = _clean_text(cells[0].get_text(" ", strip=True)).rstrip("：:")
        value = _clean_text(cells[1].get_text(" ", strip=True))
        fields[label] = value
    return fields.get("姓名", ""), fields.get("担任职务", "")


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物目录顺序抓取并解析各领导详情表格。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#Left_Nav > li > a[title][href]"):
        listed_name = _clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", listed_name) or listed_name in seen:
            continue
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        response = requests.get(
            detail_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0", "Referer": base_url},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = _extract_profile(response.text)
        if name != listed_name or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_guizhou_healthcare_profile_details_v1",
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
