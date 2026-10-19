from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"[\s\u200b]+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"^职\s*务\s*[:：]\s*", "", duty)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_detail_duty(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    article = soup.select_one(".article") or soup
    text = normalize_space(article.get_text(" ", strip=True))
    match = re.search(r"职\s*务\s*[:：]\s*(?P<duty>.+?)\s*(?:工作职责|个人简介|扫一扫)", text)
    if not match:
        return ""
    return clean_duty(match.group("duty"))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.hunan.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_nav_list_bounded_detail",
        "collector": "static_http",
        "parser": "page_hunan_science_leader_bounded_details_v1",
        "leader_region_selector": "#navbox .kjt-top-cont:first-of-type",
        "name_selector": ".kjt-top-tld h1, .list-10 li a",
        "duty_selector": "detail .article text between 职务 and 工作职责",
        "detail_link_selector": ".kjt-top-tld a[href], .list-10 li a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": ["#navbox .kjt-top-cont:first-of-type"],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "bounded_manual",
            "detail_collector_type": "static_http",
            "detail_link_selector": ".kjt-top-tld a[href], .list-10 li a[href]",
            "detail_parser": "detail_hunan_science_article_duty_v1",
            "detail_name_selector": "",
            "detail_duty_selector": ".article text between 职务 and 工作职责",
            "detail_content_selector": ".article",
            "max_detail_links": 8,
        },
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "#navbox .kjt-top-cont:first-of-type",
                "name_selector": ".kjt-top-tld h1, .list-10 li a",
                "duty_selector": "detail .article text between 职务 and 工作职责",
                "detail_link_selector": ".kjt-top-tld a[href], .list-10 li a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": ["#navbox .kjt-top-cont:first-of-type"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "列表页只列姓名，职务需要从对应领导详情页字段读取"},
        },
    }


def collect_leader_links(soup: BeautifulSoup, final_url: str) -> list[tuple[str, str]]:
    region = soup.select_one("#navbox .kjt-top-cont")
    if region is None:
        return []

    links: list[tuple[str, str]] = []
    top_link = region.select_one(".kjt-top-tld a[href]")
    if top_link:
        name_node = top_link.select_one("h1")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else top_link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, top_link.get("href", ""))
        if _is_detail_url(detail_url, final_url):
            links.append((name, detail_url))

    for link in region.select(".list-10 li a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, link.get("href", ""))
        if _is_detail_url(detail_url, final_url):
            links.append((name, detail_url))
    return links[:8]


def _is_detail_url(detail_url: str, base_url: str) -> bool:
    parsed_detail = urlparse(detail_url)
    return (
        parsed_detail.netloc.lower() == urlparse(base_url).netloc.lower()
        and urldefrag(detail_url)[0].rstrip('/') != urldefrag(base_url)[0].rstrip('/')
        and parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for name, detail_url in collect_leader_links(soup, final_url):
        if not is_name(name) or name in seen_names:
            continue
        duty = ""
        try:
            duty = parse_detail_duty(fetch_html(detail_url))
        except Exception:
            duty = ""
        if not duty or len(duty) > 120:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=#navbox first 组织机构 block；fields=8 leader links + detail 职务；detail_chain=8",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1381"
    main(rule_id_value)
