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
    "rule_id": "1801",
    "domain": "mzw.jiangsu.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "jiangsu_ethnic_religious_directory_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_ethnic_religious_directory_profiles_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情页简介与分管工作相邻；仅在简介区域提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail_html(detail_url: str, attempt_offset: int) -> str:
    """通过公共在线HTTP能力读取详情页，不落地缓存。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    return result.html


def extract_profile(detail_html: str) -> tuple[str, str]:
    """仅在当前人物详情页的简介区域提取姓名和完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    name_node = soup.select_one(".main-content-right .ldxx span")
    intro_node = soup.select_one(".main-content-right .ldjj-txt")
    if name_node is None or intro_node is None:
        return "", ""
    name = compact_name(name_node.get_text(" ", strip=True))
    intro = clean_text(intro_node.get_text(" ", strip=True))
    duty_match = re.search(r"现任[^。]*。", intro)
    evidence = clean_text(duty_match.group(0)) if duty_match else ""
    evidence = re.sub(r"^现任\s*", "", evidence)
    evidence = re.sub(r"。\s*$", "", evidence)
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导目录DOM顺序，在线读取每个人物详情页的现任职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select("ul.xxgk_list > li.cf > a[href]"), start=1):
        listed_name = compact_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", listed_name) or listed_name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            detail_html = fetch_detail_html(detail_url, source_order)
        except Exception:
            continue
        name, evidence = extract_profile(detail_html)
        if name != listed_name or not evidence:
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
                    "strategy=custom_parse_page；list=ul.xxgk_list > li.cf > a[href]；"
                    "detail-name=.main-content-right .ldxx span；"
                    "detail-duty=.main-content-right .ldjj-txt scoped-current-sentence"
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
