from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2764",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "domain": "tyj.fujian.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "fujian_sports_leader_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_sports_leader_sidebar_v1",
    "leader_region_selector": ".ld_list.down > li > a[href]",
    "name_selector": "h4",
    "duty_selector": "span",
    "detail_link_selector": "self[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_sidebar_links",
    },
    "risk_flag": "领导详情页同时包含领导活动新闻；抽取范围须严格限定在结构化领导侧栏",
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


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导侧栏DOM顺序抽取姓名、原始职务和独立人物链接。"""
    if not html:
        # 旧个人目录已失效；仅从其上级领导栏目动态发现当前入口。
        from crawler_core.fetcher import decode_response_text, requests_get_html

        response = requests_get_html(str(page_rule["url"]), timeout=20, verify=True)
        if response.status_code == 404:
            listing_url = urljoin(str(page_rule["url"]), "../")
            listing = requests_get_html(listing_url, timeout=20, verify=True)
            listing.raise_for_status()
            listing_soup = BeautifulSoup(decode_response_text(listing), "html.parser")
            meta = listing_soup.select_one('meta[http-equiv="refresh"],meta[http-equiv="Refresh"]')
            match = re.search(r"url\s*=\s*([^;]+)", str(meta.get("content", "")) if meta else "", re.I)
            if not match:
                raise RuntimeError("领导栏目未提供当前人物入口")
            target = urljoin(listing.url, match.group(1).strip(" \"'"))
            parts, listing_parts = urlsplit(target), urlsplit(listing.url)
            if parts.netloc != listing_parts.netloc or not parts.path.startswith(listing_parts.path):
                raise RuntimeError("领导栏目跳转超出当前站点栏目")
            response = requests_get_html(target, timeout=20, verify=True)
        response.raise_for_status()
        html, final_url = decode_response_text(response), response.url
    soup = BeautifulSoup(html, "html.parser")
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name_node = link.select_one(str(page_rule["name_selector"]))
        duty_node = link.select_one(str(page_rule["duty_selector"]))
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
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
