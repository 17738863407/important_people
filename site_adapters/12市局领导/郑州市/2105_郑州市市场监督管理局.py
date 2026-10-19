from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2105", "page_type": "人物目录详情页", "structure_group": "zhengzhou_public_list_duty_or_detail_current_sentence_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_to_detail", "collector": "static_http", "parser": "page_inline_zhengzhou_public_list_duty_or_detail_current_sentence_v1",
    "leader_region_selector": ".common-box .page-list a[href]", "name_selector": ":scope > span", "duty_selector": ":scope > b；为空时详情.main-body简介现任句", "detail_link_selector": ".common-box .page-list a[href]",
    "content_scope": {"start_anchor": "机构领导", "end_anchor": "", "include_selectors": [".common-box"], "exclude_selectors": ["header", "footer", "script", "style"]},
    "detail_strategy": {"required": True, "mode": "list_duty_else_detail", "detail_collector_type": "static_http", "detail_link_selector": ".common-box .page-list a[href]", "detail_parser": "page_inline_current_sentence_when_list_duty_missing", "detail_name_selector": ".main-body", "detail_duty_selector": ".main-body简介内现任句", "detail_content_selector": ".main-body", "max_detail_links": 50},
    "risk_flag": "列表中一名人物职务字段为空；现优先保留列表强字段，仅为空时在该人物详情简介范围提取完整现任句", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_list_duty_else_detail_current_sentence",
    "locator": {"css": {"leader_region_selector": ".common-box .page-list a[href]", "name_selector": ":scope > span", "duty_selector": ":scope > b or detail_current_sentence", "detail_link_selector": "same_anchor_href"}, "api": {"enabled": False, "reason": "列表与详情原始HTML可复现提供姓名、职务和当前任职证据"}, "migration": {"source": "legacy_missing_duty_and_business_source_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def detail_current_sentence(detail_url: str, expected_name: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    scope = BeautifulSoup(response.text, "html.parser").select_one(".main-body")
    if scope is None:
        return ""
    text = clean_text(scope.get_text(" ", strip=True))
    if expected_name not in text:
        return ""
    match = re.search(r"现任[^。]{2,300}。", text)
    return clean_text(match.group(0)).removeprefix("现任").rstrip().removesuffix("。").rstrip() if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["leader_region_selector"]):
        name_node = anchor.select_one(":scope > span")
        duty_node = anchor.select_one(":scope > b")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not name or name in seen:
            continue
        if not duty:
            try:
                duty = detail_current_sentence(detail_url, name)
            except requests.RequestException:
                continue
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=page_list；evidence=list_b_or_same_detail_current_sentence；order=dom"})
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
