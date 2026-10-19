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
    "rule_id": "0078",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_amr_leader_detail_label_pairs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changsha_amr_leader_detail_label_pairs_v1",
    "leader_region_selector": "div.xxgk-list > ul > li",
    "name_selector": "同列表项a[href]文本及详情领导姓名字段",
    "duty_selector": "详情div.leaderbri中的职务字段",
    "detail_link_selector": "div.xxgk-list > ul > li a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.xxgk-list"],
        "exclude_selectors": ["header", "footer", "script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.xxgk-list > ul > li a[href]",
        "detail_parser": "page_inline_detail_label_pairs",
        "detail_name_selector": "div.leaderbri li.leadsyno:nth-of-type(2)",
        "detail_duty_selector": "div.leaderbri li.leadsyno:nth-of-type(4)",
        "detail_content_selector": "div.leaderbri",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页同时提供职务与工作分工；仅采用职务标签对应值",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_label_pairs",
    "locator": {
        "css": {
            "leader_region_selector": "div.xxgk-list > ul > li",
            "name_selector": "list_anchor_text_equals_detail_name",
            "duty_selector": "detail_leaderbri_label_pair_duty",
            "detail_link_selector": "same_list_item_anchor_href",
        },
        "api": {"enabled": False, "reason": "目录和详情原始HTML直接提供强结构字段"},
        "migration": {
            "source": "legacy_list_to_detail_custom_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def clean_duty_evidence(text: str) -> str:
    """删除职务值中的独立任职状态标记，保留全部实际职务。"""
    value = clean_text(text)
    value = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", value)
    return clean_text(value)


def fetch_detail_html(detail_url: str) -> str:
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_detail(detail_html: str) -> tuple[str, str]:
    """读取详情页标签值对，仅返回姓名和原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    nodes = soup.select("div.leaderbri li")
    fields: dict[str, str] = {}
    for index in range(0, len(nodes) - 1, 2):
        label = re.sub(r"\s+", "", clean_text(nodes[index].get_text(" ", strip=True)))
        value = clean_text(nodes[index + 1].get_text(" ", strip=True))
        if label:
            fields[label] = value
    return fields.get("领导姓名", ""), clean_duty_evidence(fields.get("职务", ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保留目录顺序，逐详情页核对姓名并提取职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        anchor = item.select_one("a[href]")
        if anchor is None:
            continue
        list_name = re.sub(r"\s+", "", clean_text(anchor.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        try:
            name, duty = parse_detail(fetch_detail_html(detail_url))
        except requests.RequestException:
            continue
        name = re.sub(r"\s+", "", name)
        if not name or name != list_name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "source_text": duty,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=leader_directory；detail=label_pairs；work_division=excluded",
            }
        )
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
