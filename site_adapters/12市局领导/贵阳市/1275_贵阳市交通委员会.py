from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1275", "page_type": "人物列表完整页", "structure_group": "人物目录链接与详情表格标签值",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc li a[href*='/ld/'][title]", "name_selector": "a[title]",
    "duty_selector": "table tr td", "detail_link_selector": ".zfxxgk_zdgkc li a[href*='/ld/'][title]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zfxxgk_zdgkc"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "普通HTTP被脚本跳转；详情raw_http只读取姓名、担任职务标签值，不做职务语义替换",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def normalize_label(value: str) -> str:
    return clean_text(value).replace(" ", "").replace("　", "").rstrip("：:")


def read_detail_fields(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all("td", recursive=False)
        for index in range(len(cells) - 1):
            label = normalize_label(cells[index].get_text(" ", strip=True))
            if label in {"姓名", "担任职务"}:
                value = clean_text(cells[index + 1].get_text(" ", strip=True))
                if value:
                    fields[label] = value
    return fields


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".zfxxgk_zdgkc li a[href*='/ld/'][title]"):
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not detail_url or detail_url in seen_urls:
            continue
        detail = fetch_html_with_strategy(detail_url, "raw_http")
        fields = read_detail_fields(detail.html)
        name, duty = fields.get("姓名", ""), fields.get("担任职务", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            raise ValueError(f"详情页缺少可靠姓名或担任职务字段：{detail.final_url}")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url,
                     "selector_summary": "机构领导目录链接及详情表格姓名、担任职务标签值"})
        seen_urls.add(detail_url)
    if not rows:
        raise ValueError("机构领导目录未发现可验证的人物详情记录")
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
