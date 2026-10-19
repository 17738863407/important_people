from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2972",
    "domain": "wsb.nmg.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "leader_directory_online_detail_duty_field_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_leader_directory_online_detail_duty_field_v1",
    "leader_region_selector": ".ldxx_box",
    "detail_link_selector": "a[href]",
    "detail_region_selector": ".ldxx_xq .r",
    "detail_strategy": {"required": True, "mode": "online_detail_duty_field"},
    "risk_flag": "首人图片与文字链接重复；按目录DOM首次出现顺序去重，详情职务保留现任前缀和原标点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩页面字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def is_person_detail_url(url: str) -> bool:
    """只接受当前领导栏目中可复现的独立人物详情路径。"""
    path = urlparse(url).path
    return bool(re.search(r"/jggk/ldxx/\d{6}/t\d+_\d+\.html$", path))


def extract_detail_duty(html: str, name: str, page_rule: dict[str, object]) -> str:
    """从详情人物区域的显式“职务”字段提取原文值。"""
    soup = BeautifulSoup(html or "", "html.parser")
    title_text = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    if name not in title_text:
        return ""

    region = soup.select_one(str(page_rule.get("detail_region_selector", "")))
    if region is None:
        return ""
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if re.match(r"^职务\s*[:：]", text):
            duty = clean_text(re.sub(r"^职务\s*[:：]\s*", "", text))
            return duty.removeprefix("现任").removesuffix("。").strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录顺序在线抓取人物详情，并提取显式职务字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select(str(page_rule.get("detail_link_selector", ""))):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url or source_url, str(link.get("href", "")))
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name)
            or not is_person_detail_url(detail_url)
            or name in seen
        ):
            continue

        result = fetch_by_raw_requests(detail_url, timeout=40)
        duty = extract_detail_duty(result.html, name, page_rule)
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": result.final_url or detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.ldxx_box a[href]；"
                    "detail=.ldxx_xq .r p；field=职务；order=directory_dom"
                ),
            }
        )

    return records


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
