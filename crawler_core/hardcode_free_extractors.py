from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


DUTY_KEYWORDS = (
    "书记",
    "主任",
    "副主任",
    "部长",
    "副部长",
    "局长",
    "副局长",
    "厅长",
    "副厅长",
    "主席",
    "副主席",
    "秘书长",
    "副秘书长",
    "委员",
    "党组",
    "党委",
    "纪检",
    "组长",
    "巡视员",
    "调研员",
    "总工程师",
    "总经济师",
    "总会计师",
    "总规划师",
    "董事长",
    "总经理",
    "副总经理",
    "院长",
    "副院长",
    "站长",
    "副站长",
    "处长",
    "副处长",
)

NOISE_WORDS = (
    "领导",
    "姓名",
    "职务",
    "分工",
    "简历",
    "信息",
    "机构",
    "首页",
    "更多",
    "正文",
    "发布时间",
    "来源",
)


def clean_text(value: object) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def compact_text(value: object) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def is_probable_name(value: object) -> bool:
    text = compact_text(value).strip(" ：:，,。；;（）()[]【】")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", text):
        return False
    return not any(word == text or word in text for word in NOISE_WORDS)


def looks_like_duty(value: object) -> bool:
    text = clean_text(value)
    return 2 <= len(text) <= 180 and any(keyword in text for keyword in DUTY_KEYWORDS)


def normalize_duty(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"^(职务|现任|担任|分管|领导分工)\s*[:：]?\s*", "", text)
    return text.strip(" ：:，,。；;")


def selector_values(page_rule: dict) -> tuple[str, str, str, str]:
    locator = page_rule.get("locator") if isinstance(page_rule.get("locator"), dict) else {}
    css = locator.get("css") if isinstance(locator.get("css"), dict) else {}
    return (
        str(css.get("leader_region_selector") or page_rule.get("leader_region_selector") or ""),
        str(css.get("name_selector") or page_rule.get("name_selector") or ""),
        str(css.get("duty_selector") or page_rule.get("duty_selector") or ""),
        str(css.get("detail_link_selector") or page_rule.get("detail_link_selector") or ""),
    )


def safe_select(scope: Tag | BeautifulSoup, selector: str) -> list[Tag]:
    selector = selector.strip()
    if not selector or any(token in selector for token in ("->", " paragraph", " mapped ", "正文")):
        return []
    try:
        return [node for node in scope.select(selector) if isinstance(node, Tag)]
    except Exception:
        return []


def region_nodes(soup: BeautifulSoup, page_rule: dict) -> list[Tag | BeautifulSoup]:
    leader_selector, _name_selector, _duty_selector, _detail_selector = selector_values(page_rule)
    nodes = safe_select(soup, leader_selector)
    if nodes:
        return nodes
    candidates: list[Tag] = []
    for selector in ["main", "#content", ".content", ".main", ".leader", ".ldxx", ".article", "body"]:
        candidates.extend(safe_select(soup, selector))
    return candidates[:8] or [soup]


def text_lines(node: Tag | BeautifulSoup) -> list[str]:
    lines = [clean_text(line) for line in node.get_text("\n", strip=True).splitlines()]
    return [line for line in lines if line]


def duty_from_text(text: str, name: str = "") -> str:
    source = clean_text(text)
    if name:
        source = source.replace(name, " ")
    patterns = [
        r"现任[:：]?\s*(?P<duty>[^。；;\n]{2,160})",
        r"职务[:：]\s*(?P<duty>[^。；;\n]{2,160})",
        r"(?:任|担任)[:：]?\s*(?P<duty>[^。；;\n]{2,160})",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            duty = normalize_duty(match.group("duty"))
            if looks_like_duty(duty):
                return duty
    segments = re.split(r"[。；;\n]", source)
    for segment in segments:
        segment = normalize_duty(segment)
        if looks_like_duty(segment):
            return segment
    return ""


def split_name_duty(text: str) -> tuple[str, str] | None:
    source = clean_text(text)
    patterns = [
        r"^(?P<name>[\u4e00-\u9fff·]{2,6})\s*[:：]\s*(?P<duty>.+)$",
        r"^(?P<name>[\u4e00-\u9fff·]{2,6})[，,]\s*(?P<body>.+)$",
        r"^(?P<duty>[^:：]{2,120})[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,6})$",
    ]
    for pattern in patterns:
        match = re.match(pattern, source)
        if not match:
            continue
        name = compact_text(match.group("name"))
        duty = normalize_duty(match.groupdict().get("duty") or duty_from_text(match.groupdict().get("body", ""), name))
        if is_probable_name(name) and looks_like_duty(duty):
            return name, duty
    tokens = source.split()
    if tokens and is_probable_name(tokens[0]):
        duty = normalize_duty(" ".join(tokens[1:]))
        if looks_like_duty(duty):
            return compact_text(tokens[0]), duty
    return None


def fetch_html(url: str, referer: str = "") -> tuple[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def discover_detail_links(soup: BeautifulSoup, base_url: str, page_rule: dict) -> list[tuple[str, str]]:
    _leader_selector, name_selector, _duty_selector, detail_selector = selector_values(page_rule)
    selectors = [detail_selector, name_selector, "a[href]"]
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for selector in selectors:
        for link in safe_select(soup, selector):
            href = str(link.get("href") or "").strip()
            label = clean_text(link.get_text(" ", strip=True))
            if not href or href.startswith(("javascript:", "#")):
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            if is_probable_name(label) or any(token in href.lower() for token in ("ld", "leader", "jg", "zzjg", "xxgk")):
                seen.add(absolute)
                links.append((label, absolute))
            if len(links) >= 80:
                return links
    return links


def parse_detail_page(name_hint: str, detail_url: str, page_rule: dict, referer: str) -> dict[str, str] | None:
    try:
        html, final_url = fetch_html(detail_url, referer)
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)
    name = compact_text(name_hint) if is_probable_name(name_hint) else ""
    if not name:
        for line in lines[:30]:
            found = re.search(r"姓名[:：]?\s*([\u4e00-\u9fff·]{2,6})", line)
            if found and is_probable_name(found.group(1)):
                name = compact_text(found.group(1))
                break
    duty = ""
    for line in lines:
        if name and name not in line and not any(token in line for token in ("职务", "现任", "分工")):
            continue
        duty = duty_from_text(line, name)
        if duty:
            break
        pair = split_name_duty(line)
        if pair:
            parsed_name, parsed_duty = pair
            if not name or parsed_name == name:
                name, duty = parsed_name, parsed_duty
                break
    if not is_probable_name(name) or not looks_like_duty(duty):
        return None
    return {
        "organization": str(page_rule.get("organization", "")),
        "url": str(page_rule.get("url", referer)),
        "name": name,
        "duty": duty,
        "detail_url": final_url,
        "evidence": f"{name} {duty}",
        "parser": str(page_rule.get("parser", "")),
        "selector_summary": "strategy=hardcode_free_dynamic；source=detail_page_dom；name=online_text；duty=online_text",
    }


def rows_from_inline_text(soup: BeautifulSoup, base_url: str, page_rule: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for region in region_nodes(soup, page_rule):
        for line in text_lines(region):
            pair = split_name_duty(line)
            if not pair:
                continue
            name, duty = pair
            key = (name, duty, base_url)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", base_url)),
                    "name": name,
                    "duty": duty,
                    "detail_url": base_url,
                    "evidence": line,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "strategy=hardcode_free_dynamic；source=page_dom_text；name_duty=line_pattern",
                }
            )
    return rows


def rows_from_anchor_blocks(soup: BeautifulSoup, base_url: str, page_rule: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for label, detail_url in discover_detail_links(soup, base_url, page_rule):
        name = compact_text(label)
        if not is_probable_name(name) or name in seen_names:
            continue
        seen_names.add(name)
        duty = ""
        for link in soup.find_all("a", href=True):
            if urljoin(base_url, str(link.get("href") or "")) != detail_url:
                continue
            parent_text = clean_text(link.parent.get_text(" ", strip=True) if isinstance(link.parent, Tag) else "")
            duty = duty_from_text(parent_text, name)
            break
        if duty:
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": str(page_rule.get("url", base_url)),
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": f"{name} {duty}",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "strategy=hardcode_free_dynamic；source=list_dom_anchor_block",
                }
            )
            continue
        detail_row = parse_detail_page(name, detail_url, page_rule, base_url)
        if detail_row:
            rows.append(detail_row)
    return rows


def parse_page_without_hardcoded_people(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    base_url = final_url or str(page_rule.get("url", ""))
    soup = BeautifulSoup(html, "html.parser")
    rows = rows_from_anchor_blocks(soup, base_url, page_rule)
    if rows:
        return rows
    return rows_from_inline_text(soup, base_url, page_rule)
