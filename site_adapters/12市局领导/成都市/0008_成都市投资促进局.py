from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0008",
    "page_type": "人物目录详情页",
    "structure_group": "chengdu_investment_onclick_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "chengdu_investment_onclick_details_v1",
    "leader_region_selector": ".html008 > ul.list",
    "name_selector": "li.myflex > .cont",
    "duty_selector": "详情页#myFont中‘职务：’后的相邻p",
    "detail_link_selector": "li.myflex[onclick]的window.open地址",
    "detail_timeout_seconds": 45,
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "目录没有a标签，详情地址存于onclick；详情页普通HTTP可能返回412",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空格，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def extract_detail_url(base_url: str, onclick: str) -> str:
    """从当前目录项的window.open参数中提取并校验真实详情地址。"""
    match = re.search(r"window\.open\(\s*['\"](?P<href>[^'\"]+)['\"]", onclick or "")
    if match is None:
        return ""
    detail_url = urljoin(base_url, match.group("href"))
    parsed = urlparse(detail_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if not re.fullmatch(r"/gkml/ldcy/\d+\.shtml", parsed.path):
        return ""
    return detail_url


def find_labeled_value(container: Tag, label: str) -> str:
    """在详情页标签段落后读取紧邻字段值。"""
    normalized_label = label.rstrip("：:")
    for paragraph in container.find_all("p", recursive=False):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True)).rstrip("：:")
        if paragraph_text != normalized_label:
            continue
        value_node = paragraph.find_next_sibling("p")
        return clean_text(value_node.get_text(" ", strip=True) if value_node else "").rstrip("。")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持目录顺序抓取详情页，并读取明确标注的职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    base_url = final_url or page_rule["url"]
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导目录数量异常：{len(regions)}")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in regions[0].select(":scope > li.myflex[onclick]"):
        name_node = item.select_one(":scope > .cont")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError(f"目录姓名异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"目录姓名重复：{name}")

        detail_url = extract_detail_url(base_url, str(item.get("onclick", "")))
        if not detail_url:
            raise RuntimeError(f"目录项缺少可验证详情地址：{name}")
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="browser",
            force_browser=True,
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html or "", "html.parser")
        detail_regions = detail_soup.select("#part_03 .blk01")
        if len(detail_regions) != 1:
            raise RuntimeError(f"详情正文数量异常：{name} / {len(detail_regions)}")

        detail_name_node = detail_regions[0].select_one("h1")
        detail_name = clean_name(
            detail_name_node.get_text(" ", strip=True) if detail_name_node else ""
        )
        if detail_name != name:
            raise RuntimeError(f"目录姓名与详情姓名不一致：{name} / {detail_name}")
        field_container = detail_regions[0].select_one("#myFont")
        evidence = find_labeled_value(field_container, "职务：") if field_container else ""
        if not evidence:
            raise RuntimeError(f"详情页未找到明确职务字段：{name}")

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "目录li.myflex的.cont姓名和onclick详情；详情#myFont职务标签相邻p",
            }
        )

    if not rows:
        raise RuntimeError("领导目录没有可验证的人物详情项")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
