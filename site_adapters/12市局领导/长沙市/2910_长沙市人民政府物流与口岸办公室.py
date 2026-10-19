from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2910",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_wk_leader_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".xxgk-right[voice-arealabel='领导信息列表'] .xxgk-list > ul > li",
    "name_selector": "a[href]",
    "duty_selector": "#zoom .wrap_right > dl中标题为职务的下一dd",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".xxgk-right[voice-arealabel='领导信息列表']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "a[href]",
        "detail_name_selector": "h1.article-title",
        "detail_duty_selector": "#zoom .wrap_right > dl",
        "detail_content_selector": "#zoom .wrap_right",
        "max_detail_links": 20,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """核对详情姓名并读取强结构职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = soup.select_one("h1.article-title")
    if _clean_text(title.get_text(" ", strip=True) if title else "") != expected_name:
        return ""
    for group in soup.select("#zoom .wrap_right > dl"):
        label = group.select_one("h2.title03")
        if _clean_text(label.get_text(" ", strip=True) if label else "").replace(" ", "") != "职务":
            continue
        values = group.find_all("dd", recursive=False)
        return _clean_text(values[1].get_text(" ", strip=True)) if len(values) > 1 else ""
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导目录DOM顺序在线核对各详情页姓名和职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in soup.select(
        ".xxgk-right[voice-arealabel='领导信息列表'] .xxgk-list > ul > li"
    ):
        link = item.select_one("a[href]")
        if link is None:
            continue
        name = _clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        parsed_url = urlsplit(detail_url)
        if (
            parsed_url.netloc.lower() != source_host
            or not re.search(r"/ldxx/\d{6}/t\d{8}_\d+\.html$", parsed_url.path)
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
        duty = _extract_detail_duty(detail_result.html, name)
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=css；leader=.xxgk-right[voice-arealabel='领导信息列表'] "
                    ".xxgk-list > ul > li；name=a[href]；"
                    "duty=#zoom .wrap_right > dl职务字段；detail=同域目录人物链接"
                ),
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
