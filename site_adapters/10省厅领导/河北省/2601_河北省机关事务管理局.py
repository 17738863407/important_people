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
    "rule_id": "2601",
    "page_type": "人物目录详情页",
    "structure_group": "hebei_government_affairs_sidebar_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_hebei_government_affairs_sidebar_details_v1",
    "leader_region_selector": "a[href*='/ljwj/ldxx/']",
    "name_selector": "侧栏人物链接文本",
    "duty_selector": "详情页 .ggxxt b",
    "detail_link_selector": "侧栏人物a[href]",
    "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": ["a[href*='/ljwj/ldxx/']"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "person_name_link", "detail_collector_type": "static_http", "detail_link_selector": "a[href*='/ljwj/ldxx/']", "detail_name_selector": ".ggxxt b", "detail_duty_selector": ".ggxxt b", "detail_content_selector": ".renxx", "max_detail_links": 20},
    "risk_flag": "入口本身是首人详情页并含全体人物侧栏；按侧栏顺序抓取详情，入口等值详情链接留空",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "a[href*='/ljwj/ldxx/']", "name_selector": "侧栏人物链接文本", "duty_selector": "详情页 .ggxxt b", "detail_link_selector": "侧栏人物a[href]", "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": ["a[href*='/ljwj/ldxx/']"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML侧栏人物链接和详情页明确职务字段"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def _extract_detail(detail_html: str, expected_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    field = soup.select_one(".ggxxt b")
    evidence = _clean_text(field.get_text(" ", strip=True)) if field else ""
    if not evidence.startswith(expected_name):
        return "", ""
    return _clean_text(evidence[len(expected_name) :]), evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按侧栏原始顺序在线取得各人物详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        href = link.get("href", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or "/ljwj/ldxx/" not in href or href.endswith("/ldxx/index.shtml") or name in seen:
            continue
        seen.add(name)
        candidates.append((name, urljoin(final_url, href)))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_html = html
            output_detail_url = ""
        else:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_html = response.text
            output_detail_url = detail_url
        duty, evidence = _extract_detail(detail_html, name)
        if duty:
            rows.append({"name": name, "duty": duty, "detail_url": output_detail_url, "evidence": duty, "parser": "custom_hebei_government_affairs_sidebar_details_v1", "selector_summary": "侧栏人物链接顺序；详情页 .ggxxt b 姓名+职务"})
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
