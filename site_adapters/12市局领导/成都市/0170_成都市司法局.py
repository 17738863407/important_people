from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0170",
    "page_type": "人物目录详情页",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "leader_region_selector": "ul.list.jk_list",
    "detail_link_selector": "li > a[href*='/gkml/ldcy/']",
    "detail_content_selector": "#part_03 .blk01",
    "detail_timeout_seconds": 45,
    "risk_flag": "入口与详情页普通HTTP均返回412，必须使用浏览器渲染",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空格，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def find_labeled_value(container: Tag, label: str) -> str:
    """在详情页的标签段落后读取相邻字段值。"""
    normalized_label = label.rstrip("：:")
    for paragraph in container.find_all("p", recursive=False):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True)).rstrip("：:")
        if paragraph_text != normalized_label:
            continue
        value_node = paragraph.find_next_sibling("p")
        return clean_text(value_node.get_text(" ", strip=True) if value_node else "")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目录顺序抓取人物详情页，并读取明确标注的职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导目录区域 ul.list.jk_list")

    rows: list[dict] = []
    for link in region.select(page_rule["detail_link_selector"]):
        name_node = link.select_one("p")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue

        detail_url = urljoin(base_url, clean_text(link.get("href")))
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="browser",
            force_browser=True,
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        detail_region = detail_soup.select_one(page_rule["detail_content_selector"])
        if not detail_region:
            raise RuntimeError(f"详情页未找到正文区域：{detail_url}")

        detail_name_node = detail_region.select_one("h1")
        detail_name = clean_name(
            detail_name_node.get_text(" ", strip=True) if detail_name_node else ""
        )
        if detail_name != name:
            raise RuntimeError(f"目录姓名与详情页姓名不一致：{name} / {detail_name}")

        field_container = detail_region.select_one("#myFont")
        duty = find_labeled_value(field_container, "职务：") if field_container else ""
        if not duty:
            raise RuntimeError(f"详情页未找到明确职务字段：{detail_url}")

        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_chengdu_justice_detail_v1",
                "selector_summary": (
                    "list=ul.list.jk_list > li > a[href*='/gkml/ldcy/']；"
                    "detail=#part_03 .blk01；name=h1；duty=#myFont中职务标签的相邻p"
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
