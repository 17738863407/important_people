from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2199",
    "page_type": "人物表格页",
    "structure_group": "当前领导班子文章人物简介现任句",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#zoomcon p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#zoomcon"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "当前官方领导班子文章直接展示人物简介；只提取各人物段落内完整现任句，不把工作分工作为职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白，并清理标点前空格。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取人物简介中的姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#zoomcon")
    if content is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·]{2,4})，", text)
        current_match = re.search(r"现任[^。]*。", text)
        if name_match is None or current_match is None:
            continue
        name = name_match.group(1)
        evidence = clean_text(current_match.group(0)).removeprefix("现任").removesuffix("。")
        if name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": "官方领导分工栏目当前文章#zoomcon人物简介完整现任句",
            }
        )
        seen.add(name)

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def fetch_current_leader_article(page_rule: dict) -> object:
    """配置文章失效时，从同站领导分工栏目动态发现当前文章。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url", ""))
    try:
        return fetch_html_with_strategy(entry_url, "raw_http")
    except Exception as entry_error:
        listing_url = urljoin(entry_url, "../")
        listing_result = fetch_html_with_strategy(listing_url, "raw_http")
        soup = BeautifulSoup(listing_result.html, "html.parser")
        listing_parts = urlsplit(listing_result.final_url)
        expected_prefix = listing_parts.path.rstrip("/") + "/content/"
        for link in soup.select("a[href]"):
            title = clean_text(link.get_text(" ", strip=True))
            candidate = urljoin(listing_result.final_url, str(link.get("href") or ""))
            parts = urlsplit(candidate)
            if "领导班子" not in title:
                continue
            if parts.netloc.lower() != listing_parts.netloc.lower():
                continue
            if not parts.path.startswith(expected_prefix):
                continue
            if not re.search(r"/post_\d+\.html$", parts.path):
                continue
            return fetch_html_with_strategy(
                candidate,
                "raw_http",
                referer=listing_result.final_url,
            )
        raise RuntimeError(f"配置入口失效且领导分工栏目未发现当前文章：{entry_error}")


def main(output_dir: Path | None) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.models import PersonRecord
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        make_failure_record,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(PAGE_RULE)
    try:
        page_result = fetch_current_leader_article(page_rule)
        raw_rows = parse_page(page_result.html, page_result.final_url, page_rule)
        if not raw_rows:
            raise RuntimeError("当前领导班子文章解析结果为空")
        records = [
            PersonRecord(
                organization=str(page_rule.get("organization", "")),
                url=str(page_rule.get("url", "")),
                name=row["name"],
                duty=row["duty"],
                evidence=row["evidence"],
                detail_url=row["detail_url"],
                confidence=str(page_rule.get("confidence", "high")),
                parser=str(page_rule.get("parser", "")),
                selector_summary=row["selector_summary"],
                province=str(page_rule.get("province", "")),
                city=str(page_rule.get("city", "")),
                script_sequence=normalize_script_sequence(page_rule.get("rule_id")),
            )
            for row in raw_rows
        ]
    except Exception as error:
        records = [make_failure_record(page_rule, str(error))]

    normalize_record_source_urls(page_rule, records)
    prepare_records_for_export(records)
    for record in records:
        if not record.script_sequence:
            record.script_sequence = normalize_script_sequence(page_rule.get("rule_id"))
        if not record.selector_summary:
            record.selector_summary = "官方领导分工栏目动态文章及#zoomcon人物简介"
    output_name = build_output_name(str(page_rule.get("rule_id", "")), str(page_rule.get("organization", "机构")))
    output_path = (output_dir or project_dir / "outputs") / output_name
    export_records(output_path, records)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    output_dir_value = None
    main(output_dir_value)
