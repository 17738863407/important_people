from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3793", "domain": "zgqingyang.gov.cn", "page_type": "同页四套班子领导卡片",
    "load_mode": "静态HTML", "fetch_mode": "raw_http", "force_browser": False, "extract_mode": "list_direct",
    "collector": "raw_http", "parser": "page_inline_qingyang_people_congress_v2",
    "inline_parser_handles_fetch": True, "inline_fetch_collector": "raw_http",
    "leader_region_selector": "#swld-rdld", "name_selector": "h3.title a", "duty_selector": "span.job",
    "detail_link_selector": "h3.title a[href]", "content_scope": {"start_anchor": "市人大领导", "end_anchor": "", "include_selectors": ["#swld-rdld"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "增强请求会跟随脚本跳转至无领导数据的wca页面，必须保留原始HTTP响应并只取市人大专属ID区域", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    if not html.strip():
        from crawler_core.fetcher import fetch_by_raw_requests

        fetch_result = fetch_by_raw_requests(str(page_rule.get("url", "")), timeout=30)
        html = fetch_result.html
        final_url = fetch_result.final_url

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#swld-rdld")
    if not region:
        raise RuntimeError("原始HTTP响应缺少市人大领导区域：#swld-rdld")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for item in region.select("li"):
        link = item.select_one("h3.title a[href]")
        duty_node = item.select_one("span.job")
        if not link or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True)).lstrip("：:")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
