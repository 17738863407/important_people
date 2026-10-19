from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3876",
    "page_type": "人物目录详情页",
    "structure_group": "smx_government_leader_directory_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_smx_government_leaders_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.onewz",
    "name_selector": "li a[href] .qians",
    "duty_selector": ".leader-position .leaderItem中标签为职务的.itemValue",
    "detail_link_selector": "li a[href]",
    "detail_timeout_seconds": 30,
    "risk_flag": "入口页仅列姓名和日期，职务必须从对应详情页的明确字段提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def find_labeled_value(soup: BeautifulSoup, label: str) -> str:
    """在详情页人物信息区按明确字段标签取得对应值。"""
    for item in soup.select(".leader-position .leaderItem"):
        label_node = item.select_one(".itemName")
        value_node = item.select_one(".itemValue")
        normalized_label = clean_name(label_node.get_text(" ", strip=True) if label_node else "")
        normalized_label = normalized_label.rstrip("：:")
        if normalized_label == label and value_node is not None:
            return clean_text(value_node.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口名单原始顺序抓取详情页的姓名和职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到政府领导名单区域")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        name_node = link.select_one(".qians")
        expected_name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", expected_name) or not detail_url:
            continue

        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        detail_name = clean_name(find_labeled_value(detail_soup, "姓名"))
        duty = find_labeled_value(detail_soup, "职务")
        if detail_name != expected_name or not duty:
            raise RuntimeError(
                f"详情页姓名或职务字段不完整：{expected_name} / {detail_result.final_url}"
            )
        if detail_name in seen_names:
            continue

        seen_names.add(detail_name)
        rows.append(
            {
                "name": detail_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": (
                    "entry=ul.onewz li a[href] .qians；"
                    "detail=.leader-position .leaderItem明确姓名和职务字段"
                ),
            }
        )

    if not rows:
        raise RuntimeError("政府领导详情页未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
