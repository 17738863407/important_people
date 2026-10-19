from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from crawler_core.fetcher import current_fetch_deadline, fetch_html_with_strategy, inherit_fetch_deadline


DUTY_KEYWORD_RE = re.compile(
    r"(书记|副书记|主任|副主任|局长|副局长|厅长|副厅长|部长|副部长|"
    r"主席|副主席|秘书长|副秘书长|委员|党组|党委|纪检|巡视员|调研员|"
    r"总工程师|总经济师|总会计师|董事长|总经理|院长|副院长|校长|副校长|"
    r"省长|副省长|市长|副市长|处长|副处长|所长|副所长|会长|副会长)"
)

SKIP_NAME_WORDS = {
    "领导",
    "姓名",
    "职务",
    "详情",
    "更多",
    "简介",
    "分工",
    "机构",
    "首页",
    "政府",
    "部门",
}


def compact_text(value: object) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def compact_name(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0:：,，;；]+", "", str(value or "")).strip()


def is_probable_name(value: object) -> bool:
    name = compact_name(value)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return False
    return not any(word in name for word in SKIP_NAME_WORDS)


def looks_like_duty(value: object) -> bool:
    text = compact_text(value)
    return 2 <= len(text) <= 140 and bool(DUTY_KEYWORD_RE.search(text))


def make_row(page_rule: dict[str, Any], final_url: str, name: str, duty: str, detail_url: str, evidence: str) -> dict[str, str]:
    return {
        "organization": str(page_rule.get("organization", "")),
        "url": str(page_rule.get("url", "")) or final_url,
        "name": compact_name(name),
        "duty": compact_text(duty),
        "detail_url": detail_url,
        "evidence": compact_text(evidence)[:500],
        "confidence": str(page_rule.get("confidence", "待人工判定")),
        "parser": str(page_rule.get("parser", "dynamic_online_extractor_v1")),
        "selector_summary": "strategy=dynamic_online_extractor；source=PAGE_RULE DOM/detail selectors",
    }


def selected_nodes(soup: BeautifulSoup, selector: str) -> list[Tag]:
    selector = str(selector or "").strip()
    if not selector:
        return []
    try:
        return [node for node in soup.select(selector) if isinstance(node, Tag)]
    except Exception:
        return []


def css_locator(page_rule: dict[str, Any], field: str) -> str:
    locator = page_rule.get("locator")
    if isinstance(locator, dict):
        css = locator.get("css")
        if isinstance(css, dict) and css.get(field):
            return str(css.get(field) or "")
    return str(page_rule.get(field, "") or "")


def extract_by_explicit_fields(
    soup: BeautifulSoup,
    page_rule: dict[str, Any],
    final_url: str,
) -> list[dict[str, str]]:
    region_selector = css_locator(page_rule, "leader_region_selector")
    name_selector = css_locator(page_rule, "name_selector")
    duty_selector = css_locator(page_rule, "duty_selector")
    detail_selector = css_locator(page_rule, "detail_link_selector")
    if not name_selector or not duty_selector:
        return []
    regions = selected_nodes(soup, region_selector) or [soup]
    rows: list[dict[str, str]] = []
    for region in regions:
        names = selected_nodes(region, name_selector)
        duties = selected_nodes(region, duty_selector)
        details = selected_nodes(region, detail_selector)
        for index, name_node in enumerate(names):
            if index >= len(duties):
                continue
            name = compact_name(name_node.get_text(" ", strip=True))
            duty = compact_text(duties[index].get_text(" ", strip=True))
            if not is_probable_name(name) or not looks_like_duty(duty):
                continue
            detail_url = ""
            if index < len(details):
                detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(details[index].get("href", "")))
            evidence_node = name_node.parent if isinstance(name_node.parent, Tag) else region
            rows.append(make_row(page_rule, final_url, name, duty, detail_url, evidence_node.get_text(" ", strip=True)))
    return dedupe_rows(rows)


def split_name_duty_from_text(text: str) -> tuple[str, str] | None:
    value = compact_text(text)
    patterns = [
        r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s*[:：]\s*(?P<duty>.+)$",
        r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+)$",
        r"^(?P<duty>.+?)\s*[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,8})$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if not match:
            continue
        name = compact_name(match.group("name"))
        duty = compact_text(match.group("duty")).strip("，,。；;")
        if is_probable_name(name) and looks_like_duty(duty):
            return name, duty
    return None


def extract_from_cards(soup: BeautifulSoup, page_rule: dict[str, Any], final_url: str) -> list[dict[str, str]]:
    region_selector = css_locator(page_rule, "leader_region_selector")
    regions = selected_nodes(soup, region_selector) or selected_nodes(soup, "li, tr, .leader, .ld, .item, .card")
    if not regions:
        regions = [soup]
    rows: list[dict[str, str]] = []
    for region in regions:
        lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue
        pair = split_name_duty_from_text(" ".join(lines[:3]))
        if pair is None:
            name = next((line for line in lines[:4] if is_probable_name(line)), "")
            duty = "；".join(line for line in lines[:8] if line != name and looks_like_duty(line))
        else:
            name, duty = pair
        if not is_probable_name(name) or not looks_like_duty(duty):
            continue
        link = region.select_one("a[href]")
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))) if link else ""
        rows.append(make_row(page_rule, final_url, name, duty, detail_url, " ".join(lines)))
    return dedupe_rows(rows)


def fetch_detail_text(detail_url: str, referer: str) -> str:
    result = fetch_html_with_strategy(
        detail_url,
        strategy="raw_http",
        timeout=15,
        referer=referer,
    )
    soup = BeautifulSoup(result.html, "html.parser")
    for tag in soup.select("script, style"):
        tag.decompose()
    return compact_text(soup.get_text(" ", strip=True))


def extract_duty_from_detail(name: str, detail_text: str) -> str:
    text = compact_text(detail_text)
    patterns = [
        rf"现任(?P<duty>[^。；;]*?{DUTY_KEYWORD_RE.pattern}[^。；;]*)",
        rf"{re.escape(name)}[，,\s]*(?P<duty>[^。；;]*?{DUTY_KEYWORD_RE.pattern}[^。；;]*)",
        rf"(?P<duty>[^。；;]*?{DUTY_KEYWORD_RE.pattern}[^。；;]*)[：:\s]+{re.escape(name)}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        duty = compact_text(match.group("duty")).strip("，,。；;：:")
        if looks_like_duty(duty):
            return duty
    return ""


def extract_from_detail_links(soup: BeautifulSoup, page_rule: dict[str, Any], final_url: str) -> list[dict[str, str]]:
    selector = css_locator(page_rule, "detail_link_selector")
    detail_strategy = page_rule.get("detail_strategy")
    if isinstance(detail_strategy, dict) and detail_strategy.get("detail_link_selector"):
        selector = str(detail_strategy.get("detail_link_selector") or selector)
    links = selected_nodes(soup, selector) if selector else []
    if not links:
        links = selected_nodes(soup, "a[href]")
    page_url = str(page_rule.get("url", "")) or final_url
    max_detail_links = 80
    detail_max_workers = 2
    if isinstance(detail_strategy, dict):
        max_detail_links = max(1, int(detail_strategy.get("max_detail_links") or max_detail_links))
        detail_max_workers = min(4, max(1, int(detail_strategy.get("detail_max_workers") or detail_max_workers)))
    candidates: list[tuple[int, Tag, str, str]] = []
    for link in links[:max_detail_links]:
        text = compact_text(link.get_text(" ", strip=True))
        href = str(link.get("href", "") or "").strip()
        if not href or href.startswith(("javascript:", "#")):
            continue
        name = compact_name(text)
        if not is_probable_name(name):
            continue
        detail_url = urljoin(final_url or page_url, href)
        candidates.append((len(candidates), link, name, detail_url))

    inherited_deadline = current_fetch_deadline()

    def extract_candidate(candidate: tuple[int, Tag, str, str]) -> tuple[int, dict[str, str] | None]:
        index, link, name, detail_url = candidate
        link_text = compact_text(link.get_text(" ", strip=True))
        try:
            with inherit_fetch_deadline(inherited_deadline):
                detail_text = fetch_detail_text(detail_url, page_url)
        except Exception:
            detail_text = compact_text(
                link.parent.get_text(" ", strip=True)
                if isinstance(link.parent, Tag)
                else link_text
            )
        duty = extract_duty_from_detail(name, detail_text)
        if not duty:
            local_pair = split_name_duty_from_text(link.parent.get_text(" ", strip=True) if isinstance(link.parent, Tag) else text)
            if local_pair:
                _local_name, duty = local_pair
        if not duty:
            return index, None
        return index, make_row(page_rule, final_url, name, duty, detail_url, detail_text or link_text)

    ordered_rows: dict[int, dict[str, str]] = {}
    if detail_max_workers == 1:
        extracted = (extract_candidate(candidate) for candidate in candidates)
        for index, row in extracted:
            if row is not None:
                ordered_rows[index] = row
    else:
        with ThreadPoolExecutor(max_workers=detail_max_workers, thread_name_prefix="dynamic-detail") as executor:
            futures = [executor.submit(extract_candidate, candidate) for candidate in candidates]
            for future in as_completed(futures):
                index, row = future.result()
                if row is not None:
                    ordered_rows[index] = row
    rows = [ordered_rows[index] for index in range(len(candidates)) if index in ordered_rows]
    return dedupe_rows(rows)


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.get("name", ""), row.get("duty", ""), row.get("detail_url", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def extract_leaders_online(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """依据 PAGE_RULE 与当前在线页面抽取人物，不使用人物名单、职务或详情页固定列表。"""
    soup = BeautifulSoup(html, "html.parser")
    for extractor in (extract_by_explicit_fields, extract_from_cards, extract_from_detail_links):
        rows = extractor(soup, page_rule, final_url)
        if rows:
            return rows
    return []
