from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0061",
    "page_type": "同级领导板块合并页",
    "structure_group": "acla_chair_and_secretariat_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "page_inline_acla_merged_leaders_v3",
    "leader_region_selector": ".acla-new-right-content .supervisor-item",
    "name_selector": ".supervisor-name",
    "duty_selector": ".supervisor-title",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "从协会介绍导航动态发现会长副会长、秘书处两个板块；秘书处只采集顶部秘书长、副秘书长卡片，不采集后续内设机构负责人",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理网页排版空白，不改写职务语义。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", value or "").strip()


def _canonical_url(value: str) -> tuple[str, str]:
    """生成忽略协议和末尾斜杠的页面比较键。"""
    parts = urlsplit(value or "")
    return parts.netloc.lower(), parts.path.rstrip("/")


def _discover_section_urls(html: str, base_url: str) -> list[tuple[str, str]]:
    """按网页导航DOM顺序发现会长副会长与秘书处页面。"""
    soup = BeautifulSoup(html, "html.parser")
    target_labels = {"会长、副会长", "秘书处"}
    ordered: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for anchor in soup.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        if label not in target_labels or label in seen_labels:
            continue
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        seen_labels.add(label)
        ordered.append((label, urljoin(base_url, href)))
    if seen_labels != target_labels:
        missing = "、".join(sorted(target_labels - seen_labels))
        raise RuntimeError(f"协会介绍导航缺少板块：{missing}")
    return ordered


def _make_row(name: str, evidence: str, selector_summary: str) -> dict[str, str]:
    """创建单条页面人物记录。"""
    return {
        "name": re.sub(r"\s+", "", name),
        "duty": evidence,
        "evidence": evidence,
        "detail_url": "",
        "confidence": "high",
        "parser": PAGE_RULE["parser"],
        "selector_summary": selector_summary,
    }


def _parse_chair_page(html: str) -> list[dict[str, str]]:
    """按会长、副会长页面卡片顺序提取姓名与职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select(".supervisor-item"):
        name_node = item.select_one(".supervisor-name")
        duty_node = item.select_one(".supervisor-title")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(_make_row(name, evidence, "会长副会长supervisor-name/title强字段"))
    return rows


def _parse_secretariat_page(html: str) -> list[dict[str, str]]:
    """按秘书处页面顺序提取顶部秘书长、副秘书长卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select(".acla-new-right-content .supervisor-item"):
        name_node = item.select_one(".supervisor-name")
        duty_node = item.select_one(".supervisor-title")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(_make_row(name, evidence, "秘书处supervisor-name/title强字段"))
    return rows


def _merge_value(current: str, incoming: str) -> str:
    """合并同一人物跨板块职务，仅去除完全相同的内容。"""
    if not incoming or incoming == current:
        return current
    if not current:
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
    """按网站导航顺序合并会长副会长与秘书处两个板块。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url") or final_url)
    sections = _discover_section_urls(html, final_url or entry_url)
    current_keys = {_canonical_url(entry_url), _canonical_url(final_url)}
    section_rows: list[list[dict[str, str]]] = []
    for label, section_url in sections:
        if _canonical_url(section_url) in current_keys:
            section_html = html
        else:
            section_html = fetch_html_with_strategy(
                section_url,
                strategy="raw_http",
                timeout=60,
            ).html
        rows = _parse_chair_page(section_html) if label == "会长、副会长" else _parse_secretariat_page(section_html)
        if not rows:
            raise RuntimeError(f"协会领导板块未解析到人物：{label}")
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
