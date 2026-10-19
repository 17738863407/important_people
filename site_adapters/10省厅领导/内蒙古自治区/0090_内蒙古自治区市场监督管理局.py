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
    "rule_id": "0090",
    "domain": "amr.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_window_detail_name_direct_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_window_detail_name_direct_role_v1",
    "leader_region_selector": ".zn-sub-ldzc-box .bd",
    "main_link_selector": "> .l .r a[title][href]",
    "other_link_selector": "> .r li a[href]",
    "detail_box_selector": ".ldxq-box",
    "detail_strategy": {"required": True, "mode": "list_to_detail_strong_fields"},
    "risk_flag": "online编排未保留入口领导模块；raw_http保留权威直出HTML；详情仅取.ldxq-box直接子强字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def direct_child(node: object, tag_name: str) -> object | None:
    """取得容器中指定标签的首个直接子节点。"""
    if not hasattr(node, "find_all"):
        return None
    for child in node.find_all(tag_name, recursive=False):
        return child
    return None


def fetch_detail_duty(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线读取详情人物框的直接姓名与职务强字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    box = soup.select_one(str(page_rule.get("detail_box_selector", "")))
    if box is None:
        return ""
    name_node = direct_child(box, "h2")
    duty_node = direct_child(box, "span")
    if name_node is None or duty_node is None:
        return ""
    if clean_name(name_node.get_text(" ", strip=True)) != expected_name:
        return ""
    return clean_text(duty_node.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗主卡片及右侧列表顺序抓取详情强字段。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    links: list[object] = []
    main_selector = str(page_rule.get("main_link_selector", "")).removeprefix("> ")
    main_link = region.select_one(main_selector)
    if main_link is not None:
        links.append(main_link)
    other_selector = str(page_rule.get("other_link_selector", "")).removeprefix("> ")
    links.extend(region.select(other_selector))

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            duty = fetch_detail_duty(detail_url, name, page_rule, source_order)
        except Exception:
            continue
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.zn-sub-ldzc-box main+other links；"
                    "detail name=.ldxq-box direct h2；duty=.ldxq-box direct span"
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
