from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1013",
    "page_type": "人物目录详情页",
    "structure_group": "hangzhou_hrss_leader_directory_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_hrss_leader_directory_detail_v1",
    "leader_region_selector": "#分页列表 .page-content",
    "name_selector": "a[href][title]",
    "duty_selector": "详情表格职务标签同行值",
    "detail_link_selector": "a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_directory_links",
        "same_host_only": True,
        "detail_name_selector": "姓名标签同行值",
        "detail_duty_selector": "职务标签同行值",
    },
    "risk_flag": "详情同时含长简历与工作职责，严格按表格标签取姓名和职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def extract_labeled_fields(html: str) -> tuple[str, str]:
    """从详情表格明确标签同行中提取姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        label = compact_name(cells[0].get_text(" ", strip=True)).rstrip("：:")
        if label in {"姓名", "职务"}:
            fields[label] = clean_text(cells[1].get_text(" ", strip=True))
    return compact_name(fields.get("姓名", "")), fields.get("职务", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM原序逐页核验姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_host = urlparse(final_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select("#分页列表 .page-content a[href][title]"):
        listed_name = compact_name(anchor.get("title", "") or anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", listed_name) or listed_name in seen:
            continue
        detail_url = urljoin(final_url, anchor.get("href", ""))
        parsed = urlparse(detail_url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != entry_host:
            continue
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        detail_name, duty = extract_labeled_fields(response.text)
        if detail_name != listed_name or not duty:
            raise ValueError(f"详情页姓名或职务字段不匹配：{detail_url}")
        seen.add(listed_name)
        records.append(
            {
                "name": listed_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "#分页列表目录DOM原序；详情表格姓名、职务标签同行值",
            }
        )

    if not records:
        raise ValueError("未在人社局领导目录及详情页中解析到有效人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
