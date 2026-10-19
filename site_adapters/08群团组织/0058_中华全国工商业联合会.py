from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0058",
    "page_type": "同级领导板块合并页",
    "structure_group": "acfic_federation_and_chamber_leaders_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "page_inline_acfic_merged_leader_cards_v3",
    "leader_region_selector": "div.content dl",
    "name_selector": "dd.name a",
    "duty_selector": "dd.name后的首个非空dd",
    "detail_link_selector": "dd.name a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "从当前网页导航动态发现工商联领导、商会领导两个板块，按导航顺序合并并排除隐藏卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理网页排版空白，不改写职务语义。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def _canonical_url(value: str) -> tuple[str, str]:
    """生成忽略协议和末尾斜杠的页面比较键。"""
    parts = urlsplit(value or "")
    return parts.netloc.lower(), parts.path.rstrip("/")


def _is_hidden(node: Tag) -> bool:
    """检查当前卡片及其祖先是否处于隐藏状态。"""
    for current in [node, *node.parents]:
        if not isinstance(current, Tag):
            continue
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in (current.get("class") or [])}
        if "display:none" in style or current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden", "")).lower() == "true" or "hidden" in classes:
            return True
    return False


def _discover_section_urls(html: str, base_url: str) -> list[str]:
    """按网页导航DOM顺序发现工商联领导与商会领导页面。"""
    soup = BeautifulSoup(html, "html.parser")
    target_labels = {"工商联领导", "商会领导"}
    ordered_urls: list[str] = []
    seen_labels: set[str] = set()
    for anchor in soup.select("a[href]"):
        label = re.sub(r"\s+", "", anchor.get_text(" ", strip=True))
        if label not in target_labels or label in seen_labels:
            continue
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        seen_labels.add(label)
        ordered_urls.append(urljoin(base_url, href))
    if seen_labels != target_labels:
        missing = "、".join(sorted(target_labels - seen_labels))
        raise RuntimeError(f"领导之窗导航缺少板块：{missing}")
    return ordered_urls


def _parse_cards(html: str, base_url: str) -> list[dict[str, str]]:
    """按单个板块的可见领导卡片DOM顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select("div.content dl"):
        if _is_hidden(card):
            continue
        name_link = card.select_one("dd.name a")
        if name_link is None:
            continue
        name = re.sub(r"\s+", "", name_link.get_text(" ", strip=True))
        evidence = ""
        name_container = name_link.find_parent("dd")
        if name_container is not None:
            for sibling in name_container.find_next_siblings("dd"):
                if "name" in (sibling.get("class") or []):
                    continue
                evidence = _clean_text(sibling.get_text(" ", strip=True))
                if evidence:
                    break
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        href = str(name_link.get("href") or "").strip()
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href) if href else "",
                "confidence": "high",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "领导之窗可见content卡片；name链接姓名；后续首个非空dd职务",
            }
        )
    return rows


def _merge_value(current: str, incoming: str) -> str:
    """合并同一人物跨板块职务，避免完全重复或包含关系造成冗余。"""
    if not incoming or incoming == current or incoming in current:
        return current
    if not current or current in incoming:
        return incoming
    return f"{current}；{incoming}"


def _merge_sections(section_rows: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    """保留首板块原序，后续板块仅追加新人物并合并同名职务。"""
    merged: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for rows in section_rows:
        for row in rows:
            existing = row_by_name.get(row["name"])
            if existing is None:
                copied = dict(row)
                merged.append(copied)
                row_by_name[copied["name"]] = copied
                continue
            existing["duty"] = _merge_value(existing["duty"], row["duty"])
            existing["evidence"] = _merge_value(existing["evidence"], row["evidence"])
    return merged


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按网站导航顺序合并工商联领导和商会领导两个板块。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url") or final_url)
    section_urls = _discover_section_urls(html, final_url or entry_url)
    current_keys = {_canonical_url(entry_url), _canonical_url(final_url)}
    section_rows: list[list[dict[str, str]]] = []
    for section_url in section_urls:
        if _canonical_url(section_url) in current_keys:
            section_html, section_final_url = html, final_url or section_url
        else:
            result = fetch_html_with_strategy(section_url, strategy="raw_http", timeout=60)
            section_html, section_final_url = result.html, result.final_url
        rows = _parse_cards(section_html, section_final_url or section_url)
        if not rows:
            raise RuntimeError(f"领导板块未解析到人物：{section_url}")
        section_rows.append(rows)
    return _merge_sections(section_rows)


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
