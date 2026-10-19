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
    "rule_id": "0252",
    "page_type": "同级领导板块合并页",
    "structure_group": "cmbc_board_and_management_profile_tables_v4",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_cmbc_merged_profiles_v4",
    "leader_region_selector": "div.information-content",
    "name_selector": ":scope > table, :scope > p",
    "duty_selector": "人物标题中的姓名后文本或董事分组标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "从关于民生导航动态发现董事会介绍、管理层介绍两个板块，按导航顺序合并同名人物职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理网页排版空白，不改写职务语义。"""
    return " ".join((value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def _canonical_url(value: str) -> tuple[str, str]:
    """生成忽略协议和末尾斜杠的页面比较键。"""
    parts = urlsplit(value or "")
    return parts.netloc.lower(), parts.path.rstrip("/")


def _discover_section_urls(html: str, base_url: str) -> list[str]:
    """按网页导航DOM顺序发现董事会介绍与管理层介绍页面。"""
    soup = BeautifulSoup(html, "html.parser")
    target_labels = {"董事会介绍", "管理层介绍"}
    ordered_urls: list[str] = []
    seen_labels: set[str] = set()
    for anchor in soup.select("a[href]"):
        label = _clean_text(anchor.get_text(" ", strip=True))
        if label not in target_labels or label in seen_labels:
            continue
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        seen_labels.add(label)
        ordered_urls.append(urljoin(base_url, href))
    if seen_labels != target_labels:
        missing = "、".join(sorted(target_labels - seen_labels))
        raise RuntimeError(f"关于民生导航缺少板块：{missing}")
    return ordered_urls


def _append_row(rows: list[dict[str, str]], name: str, evidence: str) -> None:
    """将页面强结构中的姓名和职务加入当前板块记录。"""
    compact_name = re.sub(r"\s+", "", name)
    clean_evidence = _clean_text(evidence)
    if not re.fullmatch(r"[一-鿿·]{2,4}", compact_name) or not clean_evidence:
        return
    rows.append(
        {
            "name": compact_name,
            "duty": clean_evidence,
            "evidence": clean_evidence,
            "detail_url": "",
            "confidence": "high",
            "parser": PAGE_RULE["parser"],
            "selector_summary": "information-content直属人物table标题及董事分组",
        }
    )


def _parse_content(html: str) -> list[dict[str, str]]:
    """按单页正文直属节点顺序解析个人职务标题与董事姓名分组。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.information-content")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    for child in (node for node in content.children if isinstance(node, Tag)):
        if child.name == "table":
            headings = [_clean_text(node.get_text(" ", strip=True)) for node in child.select("p")]
            heading = next((text for text in headings if text), "")
            match = re.fullmatch(r"(?P<name>[一-鿿·](?:\s*[一-鿿·]){1,3})\s+(?P<duty>.+)", heading)
            if match is not None:
                _append_row(rows, match.group("name"), match.group("duty"))
            continue
        if child.name != "p" or _clean_text(child.get_text(" ", strip=True)) != "董事":
            continue
        names_node = child.find_next_sibling("p")
        names_text = _clean_text(names_node.get_text(" ", strip=True) if names_node else "")
        for name in names_text.split():
            _append_row(rows, name, "董事")
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
    """按网站导航顺序合并董事会介绍与管理层介绍两个板块。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url") or final_url)
    section_urls = _discover_section_urls(html, final_url or entry_url)
    current_keys = {_canonical_url(entry_url), _canonical_url(final_url)}
    section_rows: list[list[dict[str, str]]] = []
    for section_url in section_urls:
        if _canonical_url(section_url) in current_keys:
            section_html = html
        else:
            section_html = fetch_html_with_strategy(
                section_url,
                strategy="raw_http",
                timeout=60,
            ).html
        rows = _parse_content(section_html)
        if not rows:
            raw_result = fetch_html_with_strategy(
                section_url,
                strategy="raw_http",
                timeout=60,
            )
            rows = _parse_content(raw_result.html)
        if not rows:
            raise RuntimeError(f"关于民生领导板块未解析到人物：{section_url}")
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
