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
    "rule_id": "2074",
    "page_type": "人物列表完整页",
    "structure_group": "shenzhen_pnr_rendered_list_profile_tables_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "chrome",
    "extract_mode": "custom_parse_page",
    "parser": "shenzhen_pnr_rendered_list_profile_tables_v1",
    "leader_region_selector": "div#postList table.table-content",
    "name_selector": "tbody > tr > td.first-td > a.document-number[href]",
    "duty_selector": "div.article-content table tr",
    "detail_link_selector": "tbody > tr > td.first-td > a.document-number[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_profile_label_table",
        "detail_content_selector": "div.article-content table",
        "detail_name_label": "姓名",
        "detail_duty_label": "职务",
        "max_detail_links": 20,
    },
    "risk_flag": "普通HTTP返回412且Playwright得到39字节无效页，需使用Chrome CDP读取接口渲染DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(value: str) -> str:
    """移除字段标签和姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _clean_text(value: str) -> str:
    """合并职务字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def _profile_fields(table: object) -> dict[str, str]:
    """按人物页表格标签读取对应值，忽略工作分工行。"""
    fields: dict[str, str] = {}
    for row in table.select("tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        label = _compact_text(cells[0].get_text(" ", strip=True))
        value = _clean_text(cells[1].get_text(" ", strip=True))
        if label and value:
            fields[label] = value
    return fields


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按渲染后目录顺序动态读取人物页强结构姓名和职务字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导目录表格命中数量异常：{len(regions)}")

    entry_url = final_url or page_rule["url"]
    entry_host = urlsplit(entry_url).netloc.lower()
    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in regions[0].select(page_rule["name_selector"]):
        name = _compact_text(link.get_text(" ", strip=True))
        detail_url = urljoin(entry_url, str(link.get("href") or ""))
        detail_parts = urlsplit(detail_url)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if detail_parts.netloc.lower() != entry_host:
            continue
        if not re.fullmatch(
            r"/gkmlpt/content/\d+/\d+/post_\d+\.html", detail_parts.path
        ):
            continue
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        candidates.append((name, detail_url))

    max_detail_links = int(page_rule["detail_strategy"]["max_detail_links"])
    if not candidates or len(candidates) > max_detail_links:
        raise RuntimeError(f"人物详情链接数量异常：{len(candidates)}")

    records: list[object] = []
    for expected_name, detail_url in candidates:
        result = fetch_html_with_strategy(detail_url, strategy="chrome", timeout=60)
        detail_soup = BeautifulSoup(result.html, "html.parser")
        tables = detail_soup.select(page_rule["detail_strategy"]["detail_content_selector"])
        field_sets = [_profile_fields(table) for table in tables]
        fields = next(
            (
                item
                for item in field_sets
                if page_rule["detail_strategy"]["detail_name_label"] in item
                and page_rule["detail_strategy"]["detail_duty_label"] in item
            ),
            {},
        )
        name = _compact_text(
            fields.get(page_rule["detail_strategy"]["detail_name_label"], "")
        )
        evidence = _clean_text(
            fields.get(page_rule["detail_strategy"]["detail_duty_label"], "")
        )
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
                detail_url=detail_url,
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
