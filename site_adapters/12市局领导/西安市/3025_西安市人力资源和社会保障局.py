from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3025",
    "page_type": "人物列表完整页",
    "structure_group": "xian_hrss_rendered_list_profile_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "parser": "xian_hrss_rendered_list_profile_fields_v1",
    "leader_region_selector": "div#virtualListPc",
    "name_selector": "a[href][title]",
    "duty_selector": "div.pure-g > div.tnm + div.txt",
    "detail_link_selector": "a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_label_fields",
        "detail_row_selector": "div.pure-g",
        "detail_label_selector": ":scope > div.tnm",
        "detail_value_selector": ":scope > div.txt",
        "max_detail_links": 20,
    },
    "risk_flag": "入口普通HTTP仅显示加载中，需渲染目录；人物页HTTP直出强结构字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def _compact_text(value: str) -> str:
    """移除标签和姓名中的排版空白。"""
    return _clean_text(value).replace(" ", "")


def _extract_profile_fields(soup: object, page_rule: dict) -> dict[str, str]:
    """读取人物页“标签：值”强结构字段。"""
    strategy = page_rule["detail_strategy"]
    fields: dict[str, str] = {}
    for row in soup.select(strategy["detail_row_selector"]):
        label_node = row.select_one(strategy["detail_label_selector"])
        value_node = row.select_one(strategy["detail_value_selector"])
        if not label_node or not value_node:
            continue
        label = _compact_text(label_node.get_text(" ", strip=True)).rstrip("：:")
        value = _clean_text(value_node.get_text(" ", strip=True))
        if label and value:
            fields[label] = value
    return fields


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按渲染目录顺序动态读取人物页姓名和职务字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导目录区域命中数量异常：{len(regions)}")

    entry_url = final_url or page_rule["url"]
    entry_host = urlsplit(entry_url).netloc.lower()
    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in regions[0].select(page_rule["name_selector"]):
        expected_name = _compact_text(str(link.get("title") or link.get_text(" ", strip=True)))
        detail_url = urljoin(entry_url, str(link.get("href") or ""))
        detail_parts = urlsplit(detail_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", expected_name):
            continue
        if detail_parts.netloc.lower() != entry_host:
            continue
        if not re.fullmatch(r"/xxgk/ldzc/[a-f0-9]+\.html", detail_parts.path):
            continue
        if expected_name in seen_names:
            raise RuntimeError(f"领导姓名重复：{expected_name}")
        seen_names.add(expected_name)
        candidates.append((expected_name, detail_url))

    max_detail_links = int(page_rule["detail_strategy"]["max_detail_links"])
    if not candidates or len(candidates) > max_detail_links:
        raise RuntimeError(f"人物详情链接数量异常：{len(candidates)}")

    records: list[object] = []
    for expected_name, detail_url in candidates:
        result = fetch_html_with_strategy(detail_url, strategy="requests", timeout=60)
        detail_soup = BeautifulSoup(result.html, "html.parser")
        fields = _extract_profile_fields(detail_soup, page_rule)
        name = _compact_text(fields.get("姓名", ""))
        evidence = _clean_text(fields.get("职务", ""))
        if name != expected_name or not evidence:
            raise RuntimeError(
                f"目录与人物页字段无法核对：{expected_name} -> {name or '空'}"
            )
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=result.final_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
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
