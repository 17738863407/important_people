from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0080", "page_type": "人物目录详情页", "structure_group": "人物目录链接与详情标签值表格",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": "div.zfxxgk_zdgkc > ul > li", "name_selector": "a[title]", "duty_selector": "table tr",
    "detail_link_selector": "div.zfxxgk_zdgkc > ul > li a[href][title]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.zfxxgk_zdgkc > ul"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "详情页字段表含姓名、担任职务、领导分工和履历，仅使用姓名与担任职务标签值", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def read_detail_fields(html: str) -> dict[str, str]:
    """读取详情字段表中明确标签对应的值。"""
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for table_row in soup.select("table tr"):
        cells = table_row.find_all(["td", "th"], recursive=False)
        for index, cell in enumerate(cells[:-1]):
            label = clean_text(cell.get_text(" ", strip=True)).replace(" ", "").rstrip("：:")
            if label in {"姓名", "担任职务"}:
                fields[label] = clean_text(cells[index + 1].get_text(" ", strip=True))
    return fields


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取人物详情页并读取姓名与担任职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("div.zfxxgk_zdgkc > ul > li"):
        link = item.select_one("a[href][title]")
        if link is None:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        fields = read_detail_fields(detail.html)
        name = fields.get("姓名", "")
        duty = fields.get("担任职务", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or not duty or name in seen:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url, "selector_summary": "人物目录链接及详情字段表姓名、担任职务标签值"})
        seen.add(name)
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
