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
    "rule_id": "1122",
    "domain": "jgsw.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_card_name_colon_role_detail_intro_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_card_name_colon_role_detail_intro_v1",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "detail_link_selector": "dd a[href][title]",
    "detail_content_selector": ".TRS_Editor",
    "detail_strategy": {"required": True, "mode": "list_to_detail_verify_intro"},
    "risk_flag": "姓名含排版空格；详情还含工作分工，不能作为职务依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_label(value: object) -> str:
    """移除姓名—职务标签中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def validate_detail(
    detail_url: str,
    expected_name: str,
    expected_duty: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> bool:
    """在线验证详情简介属于当前人物且现任句包含列表职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    region = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if region is None:
        return False
    text = clean_text(region.get_text(" ", strip=True))
    sentence_match = re.search(r"现任[^。]*。", text)
    if sentence_match is None:
        return False
    current_sentence = sentence_match.group(0)
    organization = str(page_rule.get("organization", ""))
    return expected_name in text and organization in current_sentence and expected_duty in current_sentence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物卡片顺序解析“姓名：职务”，并在线核验详情。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(region.select("dd a[href][title]"), start=1):
        label = clean_label(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,5})[：:](.+)", label)
        href = str(link.get("href", ""))
        if match is None or not href:
            continue
        name, duty = match.groups()
        if not duty or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            if not validate_detail(detail_url, name, duty, page_rule, source_order):
                continue
        except Exception:
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
                    "strategy=custom_parse_page；region=ul.provincial-leaders-inner；"
                    "person=dd a[title]；label=姓名：职务；"
                    "detail=.TRS_Editor same-name current sentence verification"
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
