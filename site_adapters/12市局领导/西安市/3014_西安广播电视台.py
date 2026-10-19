from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3014", "page_type": "领导条目跳转详情页", "structure_group": "xian_tv_detail_meta_v3",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_tv_detail_meta_v3",
    "leader_region_selector": "meta[name='Url']", "name_selector": ".txt-leader内姓名标签相邻.txt",
    "duty_selector": ".txt-leader内职务标签相邻.txt", "detail_link_selector": "meta[name='Url']",
    "detail_strategy": {"required": True, "mode": "entry_meta_url", "max_detail_links": 1},
    "risk_flag": "入口仅展示当前领导条目标题，姓名与职务须从meta Url动态指向的官方详情页标签字段取得",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def field_value(card: object, keyword: str) -> str:
    for row in card.select(".row"):
        label, value = row.select_one(".tnm"), row.select_one(".txt")
        if label and value and re.sub(r"\s+", "", clean_text(label.get_text(" ", strip=True))).rstrip("：:") == keyword:
            return clean_text(value.get_text(" ", strip=True))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    from crawler_core.fetcher import fetch_by_requests

    soup = BeautifulSoup(html or "", "html.parser")
    detail_meta = soup.select("meta[name='Url']")
    if len(detail_meta) != 1:
        raise RuntimeError(f"人物详情地址元数据数量异常：{len(detail_meta)}")
    detail_url = urljoin(final_url, clean_text(detail_meta[0].get("content", "")))
    parsed_detail = urlparse(detail_url)
    parsed_entry = urlparse(final_url)
    if parsed_detail.scheme not in {"http", "https"} or parsed_detail.netloc != parsed_entry.netloc:
        raise RuntimeError(f"人物详情地址不属于当前官网：{detail_url}")
    if parsed_entry.scheme == "https" and parsed_detail.scheme == "http":
        detail_url = parsed_detail._replace(scheme="https").geturl()

    detail_result = fetch_by_requests(detail_url)
    detail_soup = BeautifulSoup(detail_result.html or "", "html.parser")
    regions = detail_soup.select(".txt-leader")
    if len(regions) != 1:
        raise RuntimeError(f"人物详情字段区域数量异常：{len(regions)}")
    name = re.sub(r"\s+", "", field_value(regions[0], "姓名"))
    evidence = field_value(regions[0], "职务")
    if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
        raise RuntimeError(f"领导姓名或职务字段异常：{name} {evidence}")
    return [
        PersonRecord(
            organization=page_rule["organization"],
            url=page_rule["url"],
            name=name,
            duty=evidence,
            detail_url=detail_result.final_url,
            evidence=evidence,
            confidence="high",
            parser=page_rule["parser"],
        )
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
