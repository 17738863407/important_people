from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0685",
    "domain": "gdj.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "department_leader_directory_trs_intro_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_department_leader_directory_trs_intro_v1",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "detail_link_selector": "dd.ldname > a[href]",
    "detail_content_selector": ".TRS_Editor",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情简介把职务与人口学信息写在同段；正文侧栏重复全体领导姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩列表和详情中的排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_detail_duty(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线读取本人详情页，并截取人口学字段之前的连续职务片段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    title = re.sub(r"\s+", "", clean_text(soup.title.get_text(" ", strip=True) if soup.title else ""))
    if title != expected_name:
        return ""

    region = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if region is None:
        return ""
    text = clean_text(region.get_text(" ", strip=True))
    organization = re.escape(str(page_rule.get("organization", "")))
    name_prefix = rf"(?:{re.escape(expected_name)}[，,])?"
    match = re.search(
        name_prefix + rf"({organization}[^。]*?)(?=[，,](?:男|女|汉族|满族|\d{{4}}年))",
        text,
    )
    return clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物目录顺序抓取详情，并提取当前职务片段。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(region.select("dd.ldname > a[href]"), start=1):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            duty = fetch_detail_duty(detail_url, name, page_rule, source_order)
        except Exception:
            continue
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=ul.provincial-leaders-inner dd.ldname > a；"
                    "detail=.TRS_Editor；name=detail title verified；"
                    "duty=intro prefix before demographic fields"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
