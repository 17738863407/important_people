from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3496",
    "page_type": "职务分组名单页",
    "structure_group": "faw_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": "div.gsldcy:not(.gsldcyWap) dl",
    "name_selector": "dd p:first-of-type a[istitle]",
    "duty_selector": "姓名p之后、专业技术职称或出生年月p之前的连续职务p",
    "detail_link_selector": "dd p:first-of-type a[istitle][href]",
    "content_scope": {
        "start_anchor": "领导成员",
        "end_anchor": "中国一汽",
        "include_selectors": ["div.gsldcy:not(.gsldcyWap)"],
        "exclude_selectors": ["div.gsldcyWap"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "dd p:first-of-type a[istitle][href]",
        "detail_name_selector": "title",
        "detail_duty_selector": "",
        "detail_content_selector": "div.detail",
        "max_detail_links": 20,
    },
    "risk_flag": "桌面端人物分为多个同类容器，移动端另有重复gsldcyWap容器",
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


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def _extract_duty(parts: list[str]) -> str:
    """截取姓名后、专业技术职称或出生年月前的连续职务行。"""
    duty_parts: list[str] = []
    for text in parts:
        if re.fullmatch(r"\d{4}年\d{1,2}月生", text):
            break
        if re.match(r"^(?:正高级|高级).*(?:工程师|会计师|经济师)$", text):
            break
        duty_parts.append(text)
    return "".join(duty_parts)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析桌面端领导卡片，并在线核对每个独立人物详情页标题。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select("div.gsldcy:not(.gsldcyWap) dl"):
        paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in card.select("dd p")]
        paragraphs = [text for text in paragraphs if text]
        if len(paragraphs) < 2:
            continue
        name = paragraphs[0].replace(" ", "")
        if name in seen_names or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        duty = _extract_duty(paragraphs[1:])
        link = card.select_one("dd p:first-of-type a[istitle][href]")
        detail_url = urljoin(final_url, str(link.get("href", ""))) if link else ""
        parsed_url = urlsplit(detail_url)
        if parsed_url.scheme == "http":
            detail_url = parsed_url._replace(scheme="https").geturl()
            parsed_url = urlsplit(detail_url)
        if (
            not duty
            or parsed_url.netloc.lower() != source_host
            or not re.search(r"/gsldcy/\d+/index\.html$", parsed_url.path)
        ):
            continue
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        detail_title = _clean_text(
            detail_soup.title.get_text(" ", strip=True) if detail_soup.title else ""
        )
        if detail_title != name:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=css；leader=div.gsldcy:not(.gsldcyWap) dl；"
                    "name=dd p:first-of-type a[istitle]；"
                    "duty=姓名后至职称或出生年月前连续p；detail=同域人物页且title核名"
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
