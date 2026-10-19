from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

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
    "rule_id": "0995",
    "domain": "hnjyj.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_prison_list_to_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hunan_prison_list_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情TLS握手偶发失败，内部抓取允许HTTPS重试后降级HTTP；输出仍保留卡片HTTPS链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def to_http(url: str) -> str:
    """仅供TLS失败后的内部抓取降级，不改变输出链接。"""
    parts = urlsplit(url)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))


def fetch_html(session: requests.Session, url: str) -> str:
    """在线抓取详情HTML，HTTPS重试失败后降级到HTTP。"""
    last_error: requests.RequestException | None = None
    for verify in (True, False):
        try:
            if not verify:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = session.get(url, timeout=30, verify=verify)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    try:
        response = session.get(to_http(url), timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return response.text
    except requests.RequestException as exc:
        last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def extract_duty(detail_html: str) -> str:
    """从详情页职务字段提取原文，并排除后续职责与简历。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    match = re.search(r"职\s*务\s*[：:]\s*(.+?)\s*工作职责\s*[：:]", text)
    return clean_text(match.group(1)).strip("，,；;。 ") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物列表顺序在线读取详情页职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/jgld/"][title]'):
        name = re.sub(r"\s+", "", str(link.get("title", "")) or link.get_text(" ", strip=True))
        href = clean_text(str(link.get("href", "")))
        detail_url = urljoin(final_url, href)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        try:
            detail_html = fetch_html(session, detail_url)
        except requests.RequestException:
            continue
        detail_text = re.sub(r"\s+", "", BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
        duty = extract_duty(detail_html)
        if name not in detail_text or not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=a[href*=jgld][title]；detail=duty-field-before-responsibility",
            }
        )

    return records


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
