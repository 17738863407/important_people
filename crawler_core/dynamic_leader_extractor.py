from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass
class DynamicLeaderRow:
    name: str
    duty: str
    detail_url: str
    evidence: str
    selector_summary: str


def normalize_space(text: object) -> str:
    """统一网页文本空白，便于正则解析。"""
    value = unescape(str(text or ""))
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def compact_text(text: object) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def is_probable_name(text: object) -> bool:
    value = compact_text(text)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", value):
        return False
    blocked = {
        "领导",
        "局长",
        "主任",
        "主席",
        "院长",
        "书记",
        "部长",
        "厅长",
        "市长",
        "更多",
        "首页",
        "通知",
        "公告",
        "简介",
        "分工",
        "职责",
    }
    return value not in blocked


def contains_duty_word(text: object) -> bool:
    value = normalize_space(text)
    duty_words = (
        "书记",
        "副书记",
        "局长",
        "副局长",
        "主任",
        "副主任",
        "厅长",
        "副厅长",
        "部长",
        "副部长",
        "主席",
        "副主席",
        "会长",
        "副会长",
        "院长",
        "副院长",
        "校长",
        "副校长",
        "秘书长",
        "副秘书长",
        "巡视员",
        "调研员",
        "总工程师",
        "总规划师",
        "总监",
        "党委",
        "党组",
        "纪委",
        "纪检",
        "委员",
        "董事长",
        "总经理",
        "副总经理",
        "总会计师",
        "工会主席",
    )
    return any(word in value for word in duty_words)


def clean_duty(text: object) -> str:
    value = normalize_space(text)
    value = re.sub(r"^(职务|职\s*务|现任职务|领导职务|分工)\s*[:：]\s*", "", value)
    value = re.sub(r"\s*(个人简历|工作分工|简历|简介)\s*[:：].*$", "", value)
    return value.strip(" ：:，,；;。.")


def strip_noise(text: str) -> str:
    value = normalize_space(text)
    value = re.sub(r"^(姓名|领导姓名|个人简介|领导信息|局领导|厅领导|现任领导)\s*[:：]\s*", "", value)
    return value.strip()


def split_name_duty(text: object) -> tuple[str, str]:
    """从同一文本块中解析姓名和职务。"""
    value = strip_noise(normalize_space(text))
    if not value or not contains_duty_word(value):
        return "", ""

    label_match = re.search(
        r"(?:姓名|领导姓名)\s*[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,4}).{0,30}?"
        r"(?:职务|现任职务|领导职务)\s*[:：]\s*(?P<duty>[^。；;\n\r]{2,80})",
        value,
    )
    if label_match:
        name = compact_text(label_match.group("name"))
        duty = clean_duty(label_match.group("duty"))
        if is_probable_name(name) and contains_duty_word(duty):
            return name, duty

    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[\s　:：-]+(?P<duty>.{2,90})$", value)
    if match:
        name = compact_text(match.group("name"))
        duty = clean_duty(match.group("duty"))
        if is_probable_name(name) and contains_duty_word(duty):
            return name, duty

    match = re.match(r"^(?P<duty>.{2,80}?)[\s　:：-]+(?P<name>[\u4e00-\u9fff·]{2,4})$", value)
    if match:
        name = compact_text(match.group("name"))
        duty = clean_duty(match.group("duty"))
        if is_probable_name(name) and contains_duty_word(duty):
            return name, duty

    for name in re.findall(r"[\u4e00-\u9fff·]{2,4}", value):
        if not is_probable_name(name):
            continue
        left, _, right = value.partition(name)
        duty = clean_duty(right or left)
        if contains_duty_word(duty):
            return compact_text(name), duty
    return "", ""


def iter_text_blocks(soup: BeautifulSoup) -> Iterable[tuple[str, str, str]]:
    selectors = [
        "tr",
        "li",
        "p",
        "div",
        "article",
        "section",
        "dd",
        "dt",
        "a",
    ]
    seen: set[str] = set()
    for selector in selectors:
        for node in soup.select(selector):
            text = normalize_space(node.get_text(" ", strip=True))
            if not text or text in seen:
                continue
            seen.add(text)
            href = ""
            if node.name == "a":
                href = str(node.get("href") or "")
            else:
                link = node.select_one("a[href]")
                if link is not None:
                    href = str(link.get("href") or "")
            yield selector, text, href


def parse_rows_from_html(html: str, final_url: str) -> list[DynamicLeaderRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[DynamicLeaderRow] = []
    seen: set[tuple[str, str, str]] = set()
    for selector, text, href in iter_text_blocks(soup):
        name, duty = split_name_duty(text)
        if not name or not duty:
            continue
        detail_url = urljoin(final_url, href) if href else final_url
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            DynamicLeaderRow(
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=text[:180],
                selector_summary=f"dynamic_text_block={selector}",
            )
        )
    return rows


def discover_detail_links(html: str, final_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        text = normalize_space(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        title = normalize_space(link.get("title", ""))
        merged = f"{text} {title} {href}"
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        if not (is_probable_name(text) or any(word in merged for word in ("领导", "简历", "分工", "成员", "主任", "局长", "书记"))):
            continue
        url = urljoin(final_url, href)
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
        if len(links) >= 50:
            break
    return links


def fetch_detail_html(url: str) -> str:
    try:
        from crawler_core.fetcher import fetch_html_with_strategy

        return fetch_html_with_strategy(url, strategy="requests", timeout=20).html
    except Exception:
        return ""


def extract_dynamic_leader_rows(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线解析领导名单，不依赖具体人物姓名、职务或详情页链接。"""
    source_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    rows = parse_rows_from_html(html, final_url)

    if not rows:
        for detail_url in discover_detail_links(html, final_url):
            detail_html = fetch_detail_html(detail_url)
            if not detail_html:
                continue
            rows.extend(parse_rows_from_html(detail_html, detail_url))

    output: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for row in rows:
        if row.name in seen_names:
            continue
        seen_names.add(row.name)
        output.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": row.name,
                "duty": row.duty,
                "detail_url": row.detail_url,
                "evidence": row.evidence,
                "confidence": "high",
                "parser": parser,
                "selector_summary": row.selector_summary,
            }
        )
    return output
