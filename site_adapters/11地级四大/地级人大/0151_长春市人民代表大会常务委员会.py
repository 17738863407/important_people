from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0151",
    "page_type": "人物表格页",
    "structure_group": "ccrd_home_left_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ccrd_home_left_leader_table_v1",
    "leader_region_selector": "td[width='220']",
    "name_selector": "a[href]",
    "duty_selector": "tr",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "include_selectors": ["td[width='220']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "首页左栏同时包含公告等模块，需限定主任之窗和最小领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    normalized = _clean_text(value)
    normalized = normalized.replace("（女）", "").replace("(女)", "")
    return re.sub(r"\s+", "", normalized).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _detail_url(final_url: str, entry_url: str, href: str) -> str:
    href = href.strip()
    candidate = urljoin(final_url, href)
    if (
        not href
        or href.startswith(("#", "javascript:", "mailto:"))
        or _normalize_url(candidate) == _normalize_url(entry_url)
    ):
        return ""
    return candidate


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析首页左栏主任之窗，并排除同栏公告等其他模块。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find("td", attrs={"width": "220"})
    if panel is None or "主任之窗" not in panel.get_text(" ", strip=True):
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[tuple[str, str]] = set()

    director_link = panel.select_one("a[title][href]")
    director_name = ""
    if director_link is not None:
        director_name = _clean_name(
            director_link.get_text(" ", strip=True) or director_link.get("title", "")
        )
        if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", director_name):
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=entry_url,
                    name=director_name,
                    duty="主任",
                    detail_url=_detail_url(final_url, entry_url, director_link.get("href", "")),
                    evidence="主任之窗",
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="td[width='220'] 主任之窗 a[title][href]",
                )
            )
            seen.add((director_name, "主任"))

    candidates: list[tuple[int, object]] = []
    for table in panel.select("table"):
        table_text = _clean_text(table.get_text(" ", strip=True))
        if "副主任" in table_text and "秘书长" in table_text and not table.select("table"):
            candidates.append((len(table_text), table))
    if not candidates:
        return records
    leader_table = min(candidates, key=lambda item: item[0])[1]

    current_duty = ""
    for table_row in leader_table.select("tr"):
        row_text = _clean_text(table_row.get_text(" ", strip=True))
        if "副主任" in row_text:
            current_duty = "副主任"
        elif "秘书长" in row_text:
            current_duty = "秘书长"
        if current_duty not in {"副主任", "秘书长"}:
            continue
        for anchor in table_row.select("a[href]"):
            name = _clean_name(anchor.get_text(" ", strip=True))
            if name == director_name or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            key = (name, current_duty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=entry_url,
                    name=name,
                    duty=current_duty,
                    detail_url=_detail_url(final_url, entry_url, anchor.get("href", "")),
                    evidence=current_duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="主任之窗最小叶子表格 tr：职务标题 + a[href]",
                )
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
