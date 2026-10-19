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
    "rule_id": "2717",
    "domain": "tjj.fujian.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "fujian_statistics_leader_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "parser": "page_inline_fujian_statistics_leader_detail_v1",
    "leader_region_selector": ".leader_name_list .dropdown_menu-right > li > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_name_selector": ".text_align_center h3",
        "detail_duty_selector": ".text_align_center h3 + p",
    },
    "risk_flag": "目录仅含姓名，须在线读取每个人物页的姓名/职务强字段；入口页同时是首人页面",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def extract_detail(detail_html: str, strategy: dict[str, object]) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(str(strategy["detail_name_selector"]))
    duty_node = soup.select_one(str(strategy["detail_duty_selector"]))
    name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
    evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
    return name, evidence


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def fetch_current_entry(page_rule: dict[str, object]) -> object:
    """旧个人页失效时，从同站领导子页入口跟随当前人物页跳转。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url") or "")
    try:
        return fetch_html_with_strategy(entry_url, strategy="raw_http", timeout=60)
    except Exception as entry_error:
        listing_url = urljoin(entry_url, "../")
        listing_result = fetch_html_with_strategy(listing_url, strategy="raw_http", timeout=60)
        refresh_match = re.search(
            r'(?is)<meta\b[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*url=([^"\'>]+)',
            listing_result.html,
        )
        if refresh_match is None:
            raise RuntimeError(f"旧入口失效且领导子页无当前页跳转：{entry_error}")
        candidate = urljoin(listing_result.final_url, refresh_match.group(1).strip())
        listing_parts = urlsplit(listing_result.final_url)
        candidate_parts = urlsplit(candidate)
        if candidate_parts.netloc.lower() != listing_parts.netloc.lower():
            raise RuntimeError("领导子页跳转到站外地址")
        if not candidate_parts.path.startswith(listing_parts.path.rstrip("/") + "/"):
            raise RuntimeError("领导子页跳转超出当前栏目")
        return fetch_html_with_strategy(candidate, strategy="raw_http", timeout=60)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录顺序在线取得每个人物页的姓名和职务。"""
    if not html:
        entry_result = fetch_current_entry(page_rule)
        html = entry_result.html
        final_url = entry_result.final_url
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    strategy = page_rule["detail_strategy"]
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        listed_name = clean_name(link.get_text(" ", strip=True))
        candidate = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", listed_name) or listed_name in seen:
            continue
        try:
            detail_html = html if comparable_url(candidate) == entry_url else fetch_detail_html(session, candidate)
        except requests.RequestException:
            continue
        name, evidence = extract_detail(detail_html, strategy)
        if name != listed_name or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "" if comparable_url(candidate) == entry_url else candidate,
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
