from __future__ import annotations

import ast
import html
import json
import math
import re
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from crawler_core.models import PersonRecord


DETAIL_LINK_SELECTOR = "div#barrierfree_container a[href*='/art/']"
DETAIL_CONTENT_SELECTOR = "div#barrierfree_container, div.article, div.TRS_Editor, body"
PARSER_NAME = "S_WWW_NINGBO_GOV_CN_LEADER_INFO_V1"


def configure_www_ningbo_gov_cn_page_rule(page_rule: dict[str, Any]) -> None:
    """统一 www.ningbo.gov.cn 领导信息栏目选择器和解析器配置。"""
    page_rule["fetch_mode"] = "snapshot"
    page_rule["collector"] = "snapshot_html"
    page_rule["parser"] = PARSER_NAME
    page_rule["locator_strategy"] = "custom_parse_page"
    page_rule["leader_region_selector"] = DETAIL_LINK_SELECTOR
    page_rule["detail_link_selector"] = "a[href*='/art/']"
    page_rule["name_selector"] = ""
    page_rule["duty_selector"] = ""
    page_rule["confidence"] = "high"
    page_rule["profile_reusable"] = "www_ningbo_gov_cn_leader_info"
    page_rule["profile_judgement"] = "www.ningbo.gov.cn 领导信息栏目同构，实时分页接口返回人名详情链接，详情页含姓名和职务字段。"
    page_rule["filter_policy"] = "strong_no_wordlist"
    page_rule["detail_strategy"] = {
        "required": True,
        "mode": "person_name_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href*='/art/']",
        "detail_name_selector": "姓名",
        "detail_duty_selector": "职务",
        "detail_content_selector": DETAIL_CONTENT_SELECTOR,
        "detail_parser": PARSER_NAME,
        "max_detail_links": 80,
        "candidate_links": _filtered_candidate_links(page_rule),
    }
    locator = page_rule.setdefault("locator", {})
    css = locator.setdefault("css", {})
    css["leader_region_selector"] = DETAIL_LINK_SELECTOR
    css["detail_link_selector"] = "a[href*='/art/']"
    css["name_selector"] = ""
    css["duty_selector"] = ""
    css["content_scope"] = {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [], "exclude_selectors": []}
    locator["api"] = {"enabled": True, "reason": "www.ningbo.gov.cn 领导信息栏目可通过 page/build/unit 分页接口取得当前完整列表"}
    locator["migration"] = {"source": "www_ningbo_gov_cn_leader_info_profile", "verified_status": "fixed", "behavior_changed": True}


def parse_www_ningbo_gov_cn_leader_page(html_text: str, final_url: str, page_rule: dict[str, Any]) -> list[PersonRecord]:
    """解析 www.ningbo.gov.cn 领导信息页，并逐个详情页补齐职务。"""
    source_url = final_url or str(page_rule.get("url") or "")
    links = _collect_person_links(page_rule, html_text, source_url)
    records: list[PersonRecord] = []
    for name, detail_url in links:
        try:
            detail_html = _fetch_html(detail_url)
            detail_name, duty, evidence = _parse_detail_page(detail_html, name)
        except Exception:
            continue
        output_name = _clean_name(detail_name) or name
        if not output_name or not duty:
            continue
        records.append(
            PersonRecord(
                organization=str(page_rule.get("organization") or ""),
                url=str(page_rule.get("url") or source_url),
                name=output_name,
                duty=duty,
                detail_url=detail_url,
                evidence=evidence or f"www.ningbo.gov.cn 领导详情：{output_name} {duty}".strip(),
                confidence="high",
                parser=PARSER_NAME,
                selector_summary=(
                    f"api=/api-gateway/jpaas-publish-server/front/page/build/unit; "
                    f"leader={DETAIL_LINK_SELECTOR}; detail={DETAIL_CONTENT_SELECTOR}; fields=姓名/职务"
                ),
            )
        )
    return records


def _filtered_candidate_links(page_rule: dict[str, Any]) -> list[dict[str, str]]:
    strategy = page_rule.get("detail_strategy")
    if not isinstance(strategy, dict):
        return []
    source_url = str(page_rule.get("url") or "")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in strategy.get("candidate_links") or []:
        if not isinstance(item, dict):
            continue
        name = _clean_name(str(item.get("text") or ""))
        url = _normalize_detail_url(urljoin(source_url, str(item.get("url") or "")))
        if not _is_person_link(name, url, source_url) or url in seen:
            continue
        seen.add(url)
        rows.append({"text": name, "url": url, "class": str(item.get("class") or "")})
    return rows


def _collect_person_links(page_rule: dict[str, Any], html_text: str, source_url: str) -> list[tuple[str, str]]:
    live_links = _collect_live_api_links(page_rule)
    if live_links:
        return live_links
    page_links = _collect_page_and_api_links(html_text, source_url)
    if page_links:
        return page_links
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in _filtered_candidate_links(page_rule):
        name = _clean_name(item["text"])
        url = _normalize_detail_url(item["url"])
        key = _url_key(url)
        if key not in seen:
            seen.add(key)
            links.append((name, url))
    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup.select("div#barrierfree_container a[href*='/art/'], a[href*='/art/']"):
        name = _clean_name(node.get_text(" ", strip=True))
        url = _normalize_detail_url(urljoin(source_url, str(node.get("href") or "")))
        key = _url_key(url)
        if not _is_person_link(name, url, source_url) or key in seen:
            continue
        seen.add(key)
        links.append((name, url))
    return links


def _collect_live_api_links(page_rule: dict[str, Any]) -> list[tuple[str, str]]:
    page_url = str(page_rule.get("url") or "")
    if not page_url:
        return []
    try:
        current_html = _fetch_html(page_url)
    except Exception:
        return []
    soup = BeautifulSoup(current_html, "html.parser")
    fragments: list[str] = []
    for script in soup.find_all("script"):
        query_text = str(script.get("querydata") or "").strip()
        unit_url = str(script.get("url") or "").strip()
        if not query_text or "page/build/unit" not in unit_url:
            continue
        try:
            query_data = ast.literal_eval(query_text)
        except Exception:
            continue
        if not isinstance(query_data, dict):
            continue
        local_query = dict(query_data)
        local_query["paramJson"] = json.dumps(
            {"pageNo": 1, "pageSize": 99999},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            fragments.append(_fetch_pagination_fragment(urljoin(page_url, unit_url), local_query))
        except Exception:
            continue
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for fragment in fragments:
        for name, url in _extract_links_from_fragment(fragment, page_url):
            key = _url_key(url)
            if key in seen:
                continue
            seen.add(key)
            links.append((name, url))
    return links


def _collect_page_and_api_links(html_text: str, source_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for fragment in [html_text, *_fetch_pagination_fragments(html_text, source_url)]:
        for name, url in _extract_links_from_fragment(fragment, source_url):
            key = _url_key(url)
            if key in seen:
                continue
            seen.add(key)
            links.append((name, url))
    return links


def _extract_links_from_fragment(fragment: str, source_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(fragment, "html.parser")
    links: list[tuple[str, str]] = []
    for node in soup.find_all("a", href=True):
        href = str(node.get("href") or "")
        if "/art/" not in href:
            continue
        name = _clean_name(str(node.get("title") or "") or node.get_text(" ", strip=True))
        url = _normalize_detail_url(urljoin(source_url, href))
        if _is_person_link(name, url, source_url):
            links.append((name, url))
    return links


def _fetch_pagination_fragments(html_text: str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    fragments: list[str] = []
    for node in soup.select("table.pagination[querydata][rows][count][uniturl]"):
        try:
            rows = int(str(node.get("rows") or "0"))
            count = int(str(node.get("count") or "0"))
        except ValueError:
            continue
        if rows <= 0 or count <= rows:
            continue
        query_text = str(node.get("querydata") or "").strip()
        try:
            query_data = ast.literal_eval(query_text)
        except Exception:
            continue
        if not isinstance(query_data, dict):
            continue
        unit_url = urljoin(source_url, str(node.get("uniturl") or ""))
        total_pages = math.ceil(count / rows)
        for page_no in range(2, total_pages + 1):
            local_query = dict(query_data)
            local_query["paramJson"] = json.dumps(
                {"pageNo": page_no, "pageSize": rows},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            try:
                fragments.append(_fetch_pagination_fragment(unit_url, local_query))
            except Exception:
                continue
    return fragments


def _fetch_pagination_fragment(unit_url: str, query_data: dict[str, Any]) -> str:
    url = unit_url + "?" + urlencode(query_data)
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36"
            ),
            "Accept": "application/json,text/javascript,*/*;q=0.01",
        },
    )
    with urlopen(request, timeout=25) as response:
        data = response.read()
    payload = json.loads(data.decode("utf-8"))
    return str(((payload.get("data") or {}) if isinstance(payload, dict) else {}).get("html") or "")


def _is_person_link(name: str, url: str, source_url: str) -> bool:
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
        return False
    if name in {"浙江省人民政府", "浙江政务服务网", "智能问答", "联系我们", "网站地图"}:
        return False
    parsed = urlparse(url)
    source = urlparse(source_url)
    if parsed.netloc and source.netloc and parsed.netloc != source.netloc:
        return False
    path = parsed.path.lower()
    return "/art/" in path and path.endswith((".html", ".htm"))


def _normalize_detail_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "www.ningbo.gov.cn":
        return parsed._replace(scheme="https", query="", fragment="").geturl()
    return parsed._replace(query="", fragment="").geturl()


def _url_key(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc.lower()}{parsed.path.lower()}"


def _fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36"
            )
        },
    )
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


def _parse_detail_page(detail_html: str, fallback_name: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = html.unescape(soup.get_text("\n", strip=True))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    name = _extract_labeled_value(text, "姓名") or fallback_name
    duty = _extract_labeled_value(text, "职务") or _extract_labeled_value(text, "领导职务")
    if not duty:
        duty = _extract_current_duty(text)
    duty = _clean_duty(duty)
    evidence = f"详情页字段：姓名={_clean_name(name)}；职务={duty}" if duty else f"详情页未解析到职务：{fallback_name}"
    return _clean_name(name), duty, evidence


def _extract_labeled_value(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*[:：]\s*(?P<value>.*?)(?=\n\s*(?:姓名|简历|职务|领导职务|分管范围|工作分工|办公电话|打印|关闭)\s*[:：]?|\n\s*(?:打印|关闭)\s*$|$)"
    match = re.search(pattern, text, re.S)
    if not match:
        return ""
    return _compact(match.group("value"))


def _extract_current_duty(text: str) -> str:
    match = re.search(r"(现任[^。\n；;]{3,120})", text)
    return _compact(match.group(1)) if match else ""


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _clean_duty(text: str) -> str:
    value = _compact(text)
    value = re.sub(r"^(?:职务|领导职务)\s*[:：]\s*", "", value)
    value = re.split(r"(?:分管范围|工作分工|职责分工|个人简历|简历|办公电话|打印|关闭)", value, maxsplit=1)[0]
    return _compact(value)


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" ：:;\t\r\n")
