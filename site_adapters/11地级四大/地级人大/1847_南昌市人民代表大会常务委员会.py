from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1847",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_renda_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "nanchang_renda_detail_current_sentence_v1",
    "leader_region_selector": "a[href*='/news/']",
    "name_selector": "a[href*='/news/']",
    "duty_selector": ".content p",
    "detail_link_selector": "a[href*='/news/']",
    "content_scope": {
        "include_selectors": ["a[href*='/news/']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_link_selector": "a[href*='/news/']",
        "detail_name_selector": "h1",
        "detail_duty_selector": ".content p",
        "max_detail_links": 50,
    },
    "risk_flag": "目录页含其他新闻链接，必须要求短中文姓名且详情正文含同名现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _fetch_current_sentence(detail_url: str, referer_url: str, name: str) -> tuple[str, str]:
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer_url},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    for paragraph in soup.select(".content p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if name not in text:
            continue
        match = re.search(r"(现任(?P<duty>[^。]+)。)", text)
        if match is not None:
            return _clean_text(match.group("duty")), _clean_text(match.group(1))
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序抓取人物详情，并仅在当前人物正文内提取完整现任句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href*='/news/']"):
        name = _clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        href = anchor.get("href", "").strip()
        detail_url = urljoin(final_url, href)
        if (
            not href
            or _normalize_url(detail_url) == _normalize_url(entry_url)
            or urlsplit(detail_url).hostname != urlsplit(final_url).hostname
        ):
            continue
        duty, evidence = _fetch_current_sentence(detail_url, final_url, name)
        if not duty or not evidence:
            continue
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="姓名目录链接 + 详情.content p内同名完整现任句",
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
