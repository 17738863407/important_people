from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2445',
 'domain': 'sjt.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'raw_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'html > body > div.wrap:nth-of-type(1) > div.main:nth-of-type(5) > div.content.mar_t_large '
                           '> div.row.content_bg_02 > div:nth-of-type(2) > div.trt-row.trt-row-large:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.wrap:nth-of-type(1) > div.main:nth-of-type(5) > '
                                               'div.content.mar_t_large > div.row.content_bg_02 > div:nth-of-type(2) > '
                                               'div.trt-row.trt-row-large:nth-of-type(2)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用在线列表详情链接解析'}}}


def _compact_name(text: str) -> str:
    return "".join(text.replace("\u3000", " ").replace("\u2002", " ").split())


def fetch_current_entry(page_rule: dict) -> object:
    """旧个人页失效时，从同站领导信息入口跟随当前页跳转。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url", ""))
    try:
        return fetch_html_with_strategy(entry_url, "raw_http")
    except Exception as entry_error:
        listing_url = urljoin(entry_url, "../")
        listing_result = fetch_html_with_strategy(listing_url, "raw_http")
        refresh_match = re.search(
            r'(?is)<meta\b[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*url=([^"\'>]+)',
            listing_result.html,
        )
        if refresh_match is None:
            raise RuntimeError(f"旧入口失效且领导信息入口无当前页跳转：{entry_error}")
        candidate = urljoin(listing_result.final_url, refresh_match.group(1).strip())
        listing_parts = urlsplit(listing_result.final_url)
        candidate_parts = urlsplit(candidate)
        if candidate_parts.netloc.lower() != listing_parts.netloc.lower():
            raise RuntimeError("领导信息入口跳转到站外地址")
        if not candidate_parts.path.startswith(listing_parts.path.rstrip("/") + "/"):
            raise RuntimeError("领导信息入口跳转超出当前栏目")
        return fetch_html_with_strategy(
            candidate,
            "raw_http",
            referer=listing_result.final_url,
        )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析福建省审计厅领导信息页的更多领导列表。"""
    if not html:
        entry_result = fetch_current_entry(page_rule)
        html = entry_result.html
        final_url = entry_result.final_url
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".content_bg_02 a[href]"):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = link.get("href", "").strip()
        if not text or text in {"领导信息", "简介", "分工"}:
            continue
        match = re.match(r"^(?P<name>[一-鿿]\s?[一-鿿]{1,3})\s+(?P<duty>.+)$", text)
        if not match:
            continue
        name = _compact_name(match.group("name"))
        duty = match.group("duty").strip()
        if name in seen or not duty:
            continue
        seen.add(name)
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(final_url or source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_fujian_audit_leader_links_v1",
                "selector_summary": ".content_bg_02 a；更多领导姓名职务",
            }
        )

    return rows


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
