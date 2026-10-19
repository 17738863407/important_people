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
    "rule_id": "1455",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_grain_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_grain_directory_details_v1",
    "leader_region_selector": "div.zfxxgk.main",
    "name_selector": "div.zfxxgk.main内人物文章a",
    "duty_selector": "详情#zoom内完整现任句",
    "detail_link_selector": "div.zfxxgk.main内人物文章a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["div.zfxxgk.main"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.zfxxgk.main内人物文章a[href]",
        "detail_name_selector": "#zoom正文开头",
        "detail_duty_selector": "#zoom内现任句",
        "detail_content_selector": "#zoom",
        "max_detail_links": 50,
    },
    "risk_flag": "目录同区含面包屑、栏目和javascript链接；仅接受LDXX1162下文章路径及人物姓名，详情仅在#zoom人物正文提取现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.zfxxgk.main",
            "name_selector": "div.zfxxgk.main内人物文章a",
            "duty_selector": "详情#zoom内完整现任句",
            "detail_link_selector": "div.zfxxgk.main内人物文章a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "主持|负责|分管",
                "include_selectors": ["#zoom"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录提供人物链接，详情#zoom正文直接包含姓名和完整现任句",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    """清理姓名中的网页排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    """在线获取人物详情页HTML及最终地址。"""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_current_sentence(html: str, expected_name: str) -> str:
    """仅在当前人物#zoom正文中提取完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#zoom")
    text = _clean_text(scope.get_text(" ", strip=True)) if scope else ""
    if not text.startswith(expected_name):
        return ""
    match = re.search(r"现任[^。]*。", text)
    return _clean_text(match.group(0)).removeprefix("现任").removesuffix("。") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序在线解析人物详情页完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("div.zfxxgk.main a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        candidate_url = urljoin(base_url, href)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name)
            or not re.search(r"/LDXX1162/\d{6}/t\d+_\d+\.html", candidate_url)
            or name in seen
        ):
            continue
        detail_html, detail_url = _fetch_detail(candidate_url)
        duty = _extract_current_sentence(detail_html, name)
        if not duty:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_grain_directory_details_v1",
                "selector_summary": "LDXX1162人物目录；详情#zoom正文内完整现任句",
            }
        )

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
