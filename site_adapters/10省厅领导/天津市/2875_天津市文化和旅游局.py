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
    "rule_id": "2875",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_culture_leader_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_culture_leader_details_v1",
    "leader_region_selector": ".main-news-box-left",
    "name_selector": ".main-news-box-left a[href]",
    "duty_selector": "详情.ldxx-js-box-text内完整现任句",
    "detail_link_selector": ".main-news-box-left a[href]",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [".main-news-box-left"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "left_menu_details", "detail_collector_type": "static_http", "detail_link_selector": ".main-news-box-left a[href]", "detail_name_selector": "简介开头", "detail_duty_selector": ".ldxx-js-box-text内现任句", "detail_content_selector": ".ldxx-js-box-text", "max_detail_links": 50},
    "risk_flag": "规则入口兼作首位领导详情页；详情仅在人物简介区域提取完整现任句，禁止本地快照",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".main-news-box-left", "name_selector": "a[href]", "duty_selector": ".ldxx-js-box-text内完整现任句", "detail_link_selector": "a[href]", "content_scope": {"start_anchor": "人物简介", "end_anchor": "", "include_selectors": [".ldxx-js-box-text"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "当前静态HTML左侧目录及详情人物简介直接提供姓名、现任职务和链接"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_current_sentence(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".ldxx-js-box-text")
    text = _clean_text(scope.get_text(" ", strip=True)) if scope else ""
    if not text.startswith(expected_name):
        return ""
    match = re.search(r"现任[^。]*。", text)
    return re.sub(r"^现任", "", _clean_text(match.group(0))).rstrip("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧目录DOM顺序在线解析人物简介现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_url = str(page_rule.get("url", final_url))
    base_url = final_url or entry_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".main-news-box-left a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        candidate_url = urljoin(base_url, str(link.get("href", "")))
        if candidate_url.rstrip("/") == base_url.rstrip("/"):
            detail_html, resolved_url = html, base_url
        else:
            detail_html, resolved_url = _fetch_detail(candidate_url)
        duty = _extract_current_sentence(detail_html, name)
        if not duty:
            continue
        detail_url = "" if resolved_url.rstrip("/") == entry_url.rstrip("/") else resolved_url
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                     "parser": "custom_tianjin_culture_leader_details_v1",
                     "selector_summary": "左侧人物目录；详情.ldxx-js-box-text完整现任句"})
    return rows


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
