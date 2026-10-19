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
    "rule_id": "3044",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_petition_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_petition_directory_details_v1",
    "leader_region_selector": "ul.lists.lingdao",
    "name_selector": "ul.lists.lingdao a[href]",
    "duty_selector": "详情.trs_editor_view中完整现任段",
    "detail_link_selector": "ul.lists.lingdao a[href]",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "", "include_selectors": ["ul.lists.lingdao"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "directory_details", "detail_collector_type": "static_http", "detail_link_selector": "ul.lists.lingdao a[href]", "detail_name_selector": "详情简介首段", "detail_duty_selector": ".trs_editor_view p现任段", "detail_content_selector": ".trs_editor_view", "max_detail_links": 50},
    "risk_flag": "详情正文依次含简历、现任职务和分管职责；只提取完整现任段，禁止快照和弱词表",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "ul.lists.lingdao", "name_selector": "a[href]", "duty_selector": ".trs_editor_view p现任段", "detail_link_selector": "a[href]", "content_scope": {"start_anchor": "现任", "end_anchor": "分管", "include_selectors": [".trs_editor_view"], "exclude_selectors": ["简历段", "分管段"]}},
        "api": {"enabled": False, "reason": "当前静态HTML人物列表与详情正文可直接提供姓名、完整现任句和链接"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value).replace("●", ""))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_current_paragraph(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".trs_editor_view p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if text.startswith("现任"):
            return text.removeprefix("现任").strip().removesuffix("。").replace("（兼）", "").replace("(兼)", "")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导目录DOM顺序在线解析详情完整现任段。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("ul.lists.lingdao a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_html, detail_url = _fetch_detail(urljoin(base_url, str(link.get("href", ""))))
        duty = _extract_current_paragraph(detail_html)
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                     "parser": "custom_tianjin_petition_directory_details_v1",
                     "selector_summary": "ul.lists.lingdao目录；详情.trs_editor_view完整现任段"})
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
