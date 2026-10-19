from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3425",
    "domain": "zscqj.hubei.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hubei_ip_list_to_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hubei_ip_list_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "列表页只有姓名和分工，原始职务从对应在线详情页强字段取得",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_html(session: requests.Session, url: str) -> tuple[str, str]:
    """在线取得页面HTML与最终URL。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def resolve_detail_page(session: requests.Session, directory_url: str) -> tuple[str, str]:
    """解析人物目录页中可复现的JavaScript详情跳转。"""
    html, final_url = fetch_html(session, directory_url)
    match = re.search(
        r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+\.shtml(?:#[^'\"]*)?)['\"]",
        html,
    )
    detail_url = urljoin(final_url, match.group(1)) if match else final_url
    return fetch_html(session, detail_url)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表顺序在线读取人物详情页姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    entry_host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".leader .list-b > li"):
        name_node = item.select_one("h4")
        link = item.select_one("a.btn[href]") or item.select_one(".pic a[href]")
        if not isinstance(name_node, Tag) or not isinstance(link, Tag):
            continue
        expected_name = clean_text(name_node.get_text(" ", strip=True))
        directory_url = urljoin(final_url, clean_text(str(link.get("href", ""))))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", expected_name):
            continue
        if urlparse(directory_url).netloc.lower() != entry_host:
            continue
        try:
            detail_html, detail_url = resolve_detail_page(session, directory_url)
        except requests.RequestException:
            continue
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        leader = detail_soup.select_one(".leader")
        if not isinstance(leader, Tag):
            continue
        detail_name_node = leader.select_one("h4")
        duty_node = leader.select_one("p")
        name = clean_text(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").rstrip("，,；;。")
        if name != expected_name or not duty or name in seen:
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
                "selector_summary": "strategy=custom_parse_page；list=.leader .list-b > li；detail=.leader h4 + first-p",
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
