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
    "rule_id": "1315",
    "domain": "jyj.ln.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "leader_directory_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_directory_detail_current_sentence_v1",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "detail_link_selector": "dd.ldname a[href]",
    "detail_content_selector": ".content p",
    "detail_strategy": {"required": True, "mode": "list_to_detail_current_sentence"},
    "risk_flag": "详情人物段落在现任句后继续列出主持、负责和分管职责；必须止于现任句号",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩目录和详情中的排版空白，不改变现任句语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_current_sentence(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线核验本人详情，并提取同一人物段落的完整现任句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    title = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    if not title.startswith(expected_name):
        return ""

    for paragraph in soup.select(str(page_rule.get("detail_content_selector", ""))):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text.startswith(expected_name) or "现任" not in text:
            continue
        match = re.search(r"现任[^。]*。", text)
        if match:
            return match.group(0).removeprefix("现任").removesuffix("。")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物目录顺序抓取详情，并提取完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(region.select("dd.ldname a[href]"), start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            evidence = fetch_current_sentence(detail_url, name, page_rule, source_order)
        except Exception:
            continue
        if not evidence:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=ul.provincial-leaders-inner dd.ldname a；"
                    "detail title=name verified；person=.content p startswith name；"
                    "duty=现任[^。]*。"
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
