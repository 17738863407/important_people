from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩详情正文排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_detail_page(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """从当前人物详情正文提取完整现任职务原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".article-body .trs_editor_view") or soup.select_one(".article-body")
    if content is None:
        return None
    text = clean_text(content.get_text(" ", strip=True))
    if expected_name not in text:
        return None
    match = re.search(r"(?P<evidence>现任山西省统计局[^。]*。)", text)
    if match is None:
        return None
    evidence = re.sub(r"^现任\s*", "", match.group("evidence")).strip(" ，,。；;：: ")
    return {"name": expected_name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
            "confidence": "high", "parser": "page_inline_shanxi_stats_detail_current_sentence_v2",
            "selector_summary": "list=a[href][title] under /tjzn/ldjs/；detail=.article-body .trs_editor_view；duty=现任山西省统计局句"}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录DOM顺序动态发现并逐页解析详情。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href][title]"):
        name = re.sub(r"\s+", "", clean_text(str(link.get("title") or "")))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or "/tjzn/ldjs/" not in detail_url or detail_url.rstrip("/") == final_url.rstrip("/") or name in seen:
            continue
        detail_html = fetch_html_with_strategy(detail_url, "raw_http").html
        row = parse_detail_page(detail_html, name, detail_url)
        if row is None:
            continue
        seen.add(name)
        rows.append(row)
    return rows


PAGE_RULE = {
    "rule_id": "2742", "page_type": "多人物详情合并页", "structure_group": "shanxi_stats_list_detail", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_to_detail", "collector": "static_http", "parser": "page_inline_shanxi_stats_detail_current_sentence_v2",
    "leader_region_selector": "a[href][title]", "name_selector": "a[title]", "duty_selector": ".article-body .trs_editor_view current-duty sentence", "detail_link_selector": "a[href][title]",
    "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": [".jld", ".article-body .trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "raw_http", "detail_link_selector": "a[href][title]", "detail_name_selector": ".article-body .trs_editor_view", "detail_duty_selector": ".article-body .trs_editor_view", "detail_content_selector": ".article-body .trs_editor_view", "max_detail_links": 20},
    "risk_flag": "详情正文同时含履历和分管内容，只提取当前人物区域中完整的现任山西省统计局原句", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "detail_chain",
    "locator": {"css": {"leader_region_selector": "a[href][title]", "name_selector": "a[title]", "duty_selector": ".article-body .trs_editor_view current-duty sentence", "detail_link_selector": "a[href][title]", "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": [".jld", ".article-body .trs_editor_view"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态领导目录与人物详情正文可稳定取得姓名、现任职务和链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
