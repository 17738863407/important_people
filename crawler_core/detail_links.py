from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag

from crawler_core.fetcher import current_fetch_deadline, fetch_html_with_strategy, inherit_fetch_deadline
from crawler_core.models import PersonRecord
from crawler_core.utils import compact_text


@dataclass
class DetailLink:
    """列表页中的详情页候选链接。"""

    text: str
    url: str
    selector: str
    evidence: str


def is_probably_file_link(url: str) -> bool:
    """排除附件、图片、脚本等非 HTML 详情页。"""
    path = urlparse(url).path.lower()
    for suffix in [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".mp4",
        ".mp3",
    ]:
        if path.endswith(suffix):
            return True
    return False


def is_noise_link_text(text: str) -> bool:
    """过滤常见导航链接文本。"""
    cleaned = compact_text(text)
    if not cleaned:
        return True
    if len(cleaned) > 80:
        return True
    noise_words = [
        "首页",
        "返回",
        "主站",
        "网站地图",
        "联系我们",
        "联系方式",
        "隐私",
        "登录",
        "注册",
        "搜索",
        "更多",
        "上一页",
        "下一页",
        "尾页",
        "关闭",
        "分享到",
        "中国政府网",
    ]
    return any(word in cleaned for word in noise_words)


def is_likely_detail_url(url: str, base_url: str) -> bool:
    """判断 URL 是否像详情页。"""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if is_probably_file_link(url):
        return False
    if parsed.fragment and not parsed.path:
        return False
    path = parsed.path.lower()
    if path.endswith(("/", "/index.html", "/index.htm")):
        return False
    if ".html" in path or ".htm" in path or "/t20" in path:
        return True
    base_path = urlparse(base_url).path.rstrip("/")
    return bool(base_path and path.startswith(base_path + "/") and path != base_path)


def is_likely_named_directory_link(text: str, url: str, base_url: str) -> bool:
    """识别同栏目下以目录形式承载的人物详情页。"""
    cleaned = compact_text(text)
    if not re.fullmatch(r"[一-鿿·]{2,6}", cleaned):
        return False
    parsed = urlparse(url)
    base = urlparse(base_url)
    if parsed.netloc and base.netloc and parsed.netloc != base.netloc:
        return False
    path = parsed.path.rstrip("/")
    base_parent = str(Path(base.path.rstrip("/")).parent).replace("\\", "/")
    if not base_parent or base_parent == ".":
        return False
    return path.startswith(base_parent.rstrip("/") + "/")


def get_detail_strategy(rule: dict[str, Any]) -> dict[str, Any]:
    """读取详情链路策略。"""
    value = rule.get("detail_strategy")
    if isinstance(value, dict):
        return value
    return {}


def get_detail_link_selector(rule: dict[str, Any]) -> str:
    """按优先级获取列表页详情链接选择器。"""
    strategy = get_detail_strategy(rule)
    for value in [
        strategy.get("detail_link_selector"),
        rule.get("detail_link_selector"),
        (
            rule.get("locator", {})
            if isinstance(rule.get("locator"), dict)
            else {}
        )
        .get("css", {})
        .get("detail_link_selector", ""),
    ]:
        text = str(value or "").strip()
        if text:
            return text
    return "a[href]"


def select_link_regions(rule: dict[str, Any], soup: BeautifulSoup) -> list[Tag | BeautifulSoup]:
    """优先在领导区域中寻找详情链接。"""
    selector = str(rule.get("leader_region_selector") or "").strip()
    if not selector and isinstance(rule.get("locator"), dict):
        css_locator = rule["locator"].get("css")
        if isinstance(css_locator, dict):
            selector = str(css_locator.get("leader_region_selector") or "").strip()
    if not selector:
        return [soup]
    try:
        regions = [node for node in soup.select(selector) if isinstance(node, Tag)]
    except Exception:
        regions = []
    return regions or [soup]


def collect_detail_links(rule: dict[str, Any], html: str, final_url: str) -> list[DetailLink]:
    """从列表页中顺序收集详情页链接。"""
    base_url = final_url or str(rule.get("url", ""))
    soup = BeautifulSoup(html, "html.parser")
    selector = get_detail_link_selector(rule)
    links: list[DetailLink] = []
    seen: set[str] = set()
    regions = select_link_regions(rule, soup)
    for region in regions:
        try:
            nodes = region.select(selector)
        except Exception:
            nodes = region.select("a[href]")
        for node in nodes:
            if not isinstance(node, Tag):
                continue
            href = str(node.get("href") or "").strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            absolute_url = urljoin(base_url, href)
            text = compact_text(node.get_text(" ", strip=True))
            if absolute_url in seen:
                continue
            if is_noise_link_text(text):
                continue
            if not is_likely_detail_url(absolute_url, base_url) and not is_likely_named_directory_link(
                text,
                absolute_url,
                base_url,
            ):
                continue
            seen.add(absolute_url)
            links.append(
                DetailLink(
                    text=text,
                    url=absolute_url,
                    selector=selector,
                    evidence=compact_text(str(node))[:500],
                )
            )
    if not links and regions != [soup]:
        local_rule = dict(rule)
        local_rule["leader_region_selector"] = ""
        return collect_detail_links(local_rule, html, final_url)
    max_links = int(get_detail_strategy(rule).get("max_detail_links") or 50)
    return links[:max_links]


def build_detail_rule(rule: dict[str, Any], detail_url: str) -> dict[str, Any]:
    """构造详情页解析用规则，保留原机构和列表页 URL。"""
    strategy = get_detail_strategy(rule)
    local_rule = dict(rule)
    local_rule["parser"] = str(
        strategy.get("detail_parser")
        or rule.get("detail_parser")
        or "V003_table_compound_person_v1"
    )
    local_rule["final_url"] = detail_url
    local_rule["leader_region_selector"] = ""
    if strategy.get("detail_content_selector"):
        local_rule["leader_region_selector"] = str(strategy["detail_content_selector"])
    if strategy.get("detail_name_selector"):
        local_rule["name_selector"] = str(strategy["detail_name_selector"])
    if strategy.get("detail_duty_selector"):
        local_rule["duty_selector"] = str(strategy["detail_duty_selector"])
    if not local_rule.get("filter_policy"):
        local_rule["filter_policy"] = "weak_allow_wordlist"
    return local_rule


def choose_better_record(current: PersonRecord, candidate: PersonRecord) -> PersonRecord:
    """同一详情页同一姓名重复时，保留职务更完整的记录。"""
    if len(candidate.duty) > len(current.duty):
        return candidate
    return current


def dedupe_detail_records(records: list[PersonRecord]) -> list[PersonRecord]:
    """按姓名和详情页去重，保持详情链接顺序。"""
    best_records: dict[tuple[str, str], PersonRecord] = {}
    order: list[tuple[str, str]] = []
    for record in records:
        key = (record.name, record.detail_url)
        if not record.name or not record.detail_url:
            order.append(key)
            best_records[key] = record
            continue
        if key not in best_records:
            order.append(key)
            best_records[key] = record
            continue
        best_records[key] = choose_better_record(best_records[key], record)
    return [best_records[key] for key in order if key in best_records]


def parse_detail_chain_records(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    snapshot_path: Path | None,
    timeout_seconds: int,
) -> list[PersonRecord]:
    """受控并发抓取详情页，并严格恢复列表页原始顺序。"""
    from crawler_core.parser_registry import parse_with_registered_parser

    strategy = get_detail_strategy(rule)
    fetch_mode = str(rule.get("fetch_mode") or "").strip().lower()
    if fetch_mode == "snapshot":
        return [
            PersonRecord(
                organization=str(rule.get("organization", "")),
                url=str(rule.get("url", final_url)),
                name="",
                duty="",
                detail_url="",
                evidence="详情链页面在 snapshot 模式下不联网抓取详情页，等待 online 重试",
                confidence="失败",
                parser=str(strategy.get("detail_parser") or "V003_table_compound_person_v1"),
                snapshot_path=str(snapshot_path or ""),
                selector_summary="detail_chain=snapshot_skip",
            )
        ]
    detail_collector_type = str(strategy.get("detail_collector_type") or "static_http")
    force_browser = detail_collector_type in {"browser", "playwright", "dynamic_dom"}
    fetch_strategy = "browser" if force_browser else "raw_http"
    links = collect_detail_links(rule, html, final_url)
    if not links:
        return []
    configured_workers = int(strategy.get("detail_max_workers") or 2)
    max_workers = 1 if force_browser else min(4, max(1, configured_workers))
    inherited_deadline = current_fetch_deadline()

    def fetch_and_parse(index: int, link: DetailLink) -> tuple[int, list[PersonRecord]]:
        local_records: list[PersonRecord] = []
        try:
            with inherit_fetch_deadline(inherited_deadline):
                detail_result = fetch_html_with_strategy(
                    link.url,
                    strategy=fetch_strategy,
                    force_browser=force_browser,
                    timeout=timeout_seconds,
                    referer=final_url,
                )
                detail_rule = build_detail_rule(rule, link.url)
                detail_rows = parse_with_registered_parser(
                    detail_rule,
                    detail_result.html,
                    detail_result.final_url or link.url,
                    snapshot_path,
                )
                for row in detail_rows:
                    row.detail_url = detail_result.final_url or link.url
                    if not row.evidence:
                        row.evidence = link.evidence
                    row.selector_summary = (
                        f"detail_chain={link.selector}；detail_parser={detail_rule.get('parser', '')}"
                    )
                    local_records.append(row)
        except Exception as error:
            local_records.append(
                PersonRecord(
                    organization=str(rule.get("organization", "")),
                    url=str(rule.get("url", final_url)),
                    name="",
                    duty="",
                    detail_url=link.url,
                    evidence=f"详情页抽取失败：{error}",
                    confidence="失败",
                    parser=str(strategy.get("detail_parser") or "V003_table_compound_person_v1"),
                    snapshot_path=str(snapshot_path or ""),
                    selector_summary=f"detail_chain={link.selector}",
                )
            )
        return index, local_records

    ordered_records: dict[int, list[PersonRecord]] = {}
    if max_workers == 1:
        for index, link in enumerate(links):
            result_index, detail_records = fetch_and_parse(index, link)
            ordered_records[result_index] = detail_records
    else:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="detail-http") as executor:
            futures = {
                executor.submit(fetch_and_parse, index, link): index
                for index, link in enumerate(links)
            }
            for future in as_completed(futures):
                result_index, detail_records = future.result()
                ordered_records[result_index] = detail_records

    records = [
        record
        for index in range(len(links))
        for record in ordered_records.get(index, [])
    ]
    return dedupe_detail_records(records)
