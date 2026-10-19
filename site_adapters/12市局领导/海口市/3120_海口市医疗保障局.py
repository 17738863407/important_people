from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3120",
    "page_type": "人物目录详情页",
    "structure_group": "haikou_medical_security_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "haikou_medical_security_profiles_v1",
    "leader_region_selector": "a[title][href*='/ldxx/'][href$='.shtml']",
    "name_selector": "目录链接title",
    "duty_selector": "#zoom当前人物正文内完整现任原句",
    "detail_link_selector": "a[title][href*='/ldxx/'][href$='.shtml']",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_name_selector": "meta[name='ArticleTitle']",
        "detail_content_selector": "#zoom",
        "max_detail_links": 50,
    },
    "risk_flag": "逐一校验详情标题姓名，只在当前人物正文提取现任原句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    """压缩网页排版空白，保留原文标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def valid_detail_url(href: str, final_url: str) -> str:
    """校验医疗保障局站内人物详情页路径。"""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.search(r"/ldxx/\d{6}/[0-9a-f]+\.shtml(?:$|[?#])", detail_url, re.I):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现领导目录，并逐页提取当前人物的完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[title][href*='/ldxx/'][href$='.shtml']"):
        name = compact_text(link.get("title", ""))
        detail_url = valid_detail_url(link.get("href", ""), final_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise ValueError("领导目录未发现有效姓名详情链接")

    records: list[dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for name, detail_url in candidates:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_soup = BeautifulSoup(response.text, "html.parser")
            title = detail_soup.select_one("meta[name='ArticleTitle']")
            content = detail_soup.select_one("#zoom")
            if title is None or compact_text(title.get("content", "")) != name:
                raise ValueError(f"详情标题姓名不一致：{name}")
            if content is None:
                raise ValueError(f"详情缺少人物正文：{name}")
            text = compact_text(content.get_text(" ", strip=True))
            match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", text)
            if not match:
                raise ValueError(f"详情正文未发现现任职务原句：{name}")
            records.append(
                {
                    "name": name,
                    "duty": match.group("duty"),
                    "evidence": match.group("duty"),
                    "detail_url": response.url,
                    "selector_summary": "领导目录title姓名链接→详情标题校验→#zoom现任原句",
                }
            )
    return records


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
