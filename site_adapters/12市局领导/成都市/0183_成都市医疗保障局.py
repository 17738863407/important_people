from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0183",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "leader_region_selector": "div.html008 > ul.list",
    "person_item_selector": "li.myflex[onclick]",
    "detail_content_selector": "#part_03 .blk01",
    "detail_timeout_seconds": 45,
    "risk_flag": "列表以onclick承载详情链接，普通HTTP受412防护",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空格，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def extract_detail_path(onclick: object) -> str:
    """从当前人物项的 window.open 调用中提取详情路径。"""
    match = re.search(r"window\.open\(\s*['\"]([^'\"]+)['\"]", str(onclick or ""))
    return clean_text(match.group(1)) if match else ""


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
    """按列表DOM顺序访问人物详情页并抽取明确职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导列表区域 div.html008 > ul.list")

    rows: list[dict] = []
    for item in region.select(page_rule["person_item_selector"]):
        name_node = item.select_one("div.cont")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue

        detail_path = extract_detail_path(item.get("onclick"))
        if not detail_path:
            raise RuntimeError(f"人物项缺少可验证详情路径：{name}")
        detail_url = urljoin(base_url, detail_path)
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
            raise RuntimeError(f"列表姓名与详情页姓名不一致：{name} / {detail_name}")

        field_container = detail_region.select_one("#myFont")
        duty = find_labeled_value(field_container, "职务：") if field_container else ""
        duty = re.sub(r"[。．]\s*$", "", duty).strip()
        if not duty:
            raise RuntimeError(f"详情页未找到明确职务字段：{detail_url}")

        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_chengdu_medical_security_detail_v1",
                "selector_summary": (
                    "list=div.html008 > ul.list > li.myflex[onclick]；"
                    "name=div.cont；detail=onclick window.open；"
                    "detail_region=#part_03 .blk01；duty=#myFont中职务标签的相邻p"
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
