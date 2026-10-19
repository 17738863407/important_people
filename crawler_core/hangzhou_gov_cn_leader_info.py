from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from crawler_core.models import PersonRecord


PARSER_NAME = "S_HANGZHOU_GOV_CN_LEADER_INFO_V1"


def configure_hangzhou_gov_cn_leader_page_rule(page_rule: dict[str, Any]) -> None:
    """配置杭州政府 CMS 领导信息页，列表页用静态请求，详情页静态解析。"""
    page_rule["fetch_mode"] = str(page_rule.get("fetch_mode") or "raw_http")
    page_rule["parser"] = PARSER_NAME
    page_rule["locator_strategy"] = "custom_parse_page"
    page_rule["confidence"] = "high"
    page_rule["profile_reusable"] = "hangzhou_gov_cn_leader_info"
    page_rule["profile_judgement"] = "杭州政府 CMS 本机关负责人栏目同构，列表页为人名详情链接，详情页含领导姓名和职务字段。"
    strategy = page_rule.get("detail_strategy")
    if isinstance(strategy, dict):
        strategy["detail_collector_type"] = "static_http"
        strategy["detail_parser"] = PARSER_NAME
    locator = page_rule.setdefault("locator", {})
    locator["api"] = {"enabled": False, "reason": "静态 HTML 列表和详情页字段已能稳定解析"}
    locator["migration"] = {"source": "hangzhou_gov_cn_leader_info_profile", "verified_status": "fixed", "behavior_changed": True}


def parse_hangzhou_gov_cn_leader_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[PersonRecord]:
    """从候选人名详情链接读取杭州政府 CMS 领导姓名和职务。"""
    base_url = final_url or str(page_rule.get("url") or "")
    records: list[PersonRecord] = []
    seen: set[str] = set()
    for name, detail_url in _collect_candidate_person_links(page_rule, base_url):
        if detail_url in seen:
            continue
        seen.add(detail_url)
        try:
            detail_html = _fetch_html(detail_url)
            detail_name, duty = _parse_detail(detail_html, name)
        except Exception:
            continue
        if not detail_name or not duty:
            continue
        records.append(
            PersonRecord(
                organization=str(page_rule.get("organization") or ""),
                url=str(page_rule.get("url") or base_url),
                name=detail_name,
                duty=duty,
                detail_url=detail_url,
                evidence=f"详情页字段：领导姓名={detail_name}；职务={duty}",
                confidence="high",
                parser=PARSER_NAME,
                selector_summary="detail_links=candidate_links; fields=领导姓名/职务",
            )
        )
    return records


def _collect_candidate_person_links(page_rule: dict[str, Any], base_url: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    strategy = page_rule.get("detail_strategy")
    if not isinstance(strategy, dict):
        return rows
    base_host = urlparse(base_url).netloc
    for item in strategy.get("candidate_links") or []:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\s+", "", str(item.get("text") or ""))
        detail_url = urljoin(base_url, str(item.get("url") or ""))
        parsed = urlparse(detail_url)
        if parsed.netloc and parsed.netloc != base_host:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) and "/art/" in parsed.path:
            rows.append((name, detail_url))
    return rows


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=25) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _parse_detail(detail_html: str, fallback_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = _clean_text(soup.get_text(" ", strip=True))
    name = _extract_labeled_value(text, r"领导姓名|姓名") or fallback_name
    duty = _extract_labeled_value(text, r"职\s*务|现任职务")
    return re.sub(r"\s+", "", name), duty


def _extract_labeled_value(text: str, label_pattern: str) -> str:
    pattern = rf"(?:{label_pattern})\s*[:：]?\s*(?P<value>.*?)(?=\s*(?:领导姓名|姓名|领导照片|照片|照\s*片|职\s*务|现任职务|分管范围|领导简历|工作简历|工作分工|办公室电话|办公电话|打印|关闭)\s*[:：]?|$)"
    match = re.search(pattern, text, re.S)
    return _clean_text(match.group("value")) if match else ""


def _clean_text(value: str) -> str:
    text = html_lib.unescape(value or "")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ：:\t\r\n")
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
