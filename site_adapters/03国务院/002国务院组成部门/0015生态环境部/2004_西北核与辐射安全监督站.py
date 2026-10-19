from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2004",
    "page_type": "人物列表完整页",
    "structure_group": "nwro_leader_category_pages_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "category_pages",
    "collector": "static_http",
    "parser": "page_inline_nwro_leader_category_pages_v2",
    "leader_region_selector": ".main a[href]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".main a[href*='/t']",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".main"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "category_to_list_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".main a[href*='/t']",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "人物按入口页职务分类导航顺序输出；分类页标题为原始职务，条目文本含月日和姓名",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_category_navigation",
    "locator": {
        "css": {
            "leader_region_selector": ".main a[href]",
            "detail_link_selector": ".main a[href*='/t']",
        },
        "api": {"enabled": False, "reason": "当前入口和职务分类页静态HTML提供完整人物结构"},
        "migration": {
            "source": "legacy_offline_category_dependency_and_business_source_removed",
            "verified_status": "verified_current_raw_http_categories",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _fetch_page(session: requests.Session, url: str) -> tuple[str, str]:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    errors: list[str] = []
    for _ in range(6):
        try:
            response = session.get(url, timeout=25, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text, response.url
        except requests.RequestException as exc:
            errors.append(str(exc))
    raise RuntimeError(f"领导分类页抓取失败：{url}；{' | '.join(errors)}")


def _is_category_url(url: str) -> bool:
    return bool(re.fullmatch(r"/zwgk/jgzn/zyld/[^/]+/", urlparse(url).path))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """动态发现全部职务分类页，再按分类与条目的网页顺序提取人物。"""
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html, "html.parser")
    category_urls: list[str] = []
    for link in entry_soup.select(".main a[href]"):
        category_url = urljoin(final_url, link.get("href", ""))
        if _is_category_url(category_url) and category_url not in category_urls:
            category_urls.append(category_url)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
            "Referer": final_url,
        }
    )
    records: list[PersonRecord] = []
    seen_detail_urls: set[str] = set()
    for category_url in category_urls:
        if category_url == final_url:
            category_html, category_final_url = html, final_url
        else:
            category_html, category_final_url = _fetch_page(session, category_url)
        soup = BeautifulSoup(category_html, "html.parser")
        duty = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        if not duty or "领导" in duty:
            continue
        for link in soup.select(".main a[href*='/t']"):
            text = _clean_text(link.get_text(" ", strip=True))
            match = re.fullmatch(r"\d{2}-\d{2}\s+([\u4e00-\u9fff·\s]{2,20})", text)
            if match is None:
                continue
            name = re.sub(r"\s+", "", match.group(1))
            detail_url = urljoin(category_final_url, link.get("href", ""))
            if detail_url in seen_detail_urls:
                continue
            seen_detail_urls.add(detail_url)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url=detail_url,
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="入口职务分类导航 + 分类页标题 + 日期姓名链接",
                )
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
