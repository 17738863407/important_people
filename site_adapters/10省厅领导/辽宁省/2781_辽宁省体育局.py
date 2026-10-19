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
    "rule_id": "2781",
    "domain": "tyj.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_directory_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_directory_detail_current_sentence_v1",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "detail_link_selector": "dd.ldname a[istitle='true'][href]",
    "detail_name_selector": ".xxgk_ldlxm",
    "detail_content_selector": ".xxgk_ldr",
    "detail_strategy": {"required": True, "mode": "list_to_detail_current_sentence"},
    "risk_flag": "详情人物容器先列职责分工；只取本人简介中的完整“现任……”句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩详情文本中的排版空白，不改变原句语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def extract_current_sentence(container: object) -> str:
    """只在当前人物详情容器内提取完整现任职务原句。"""
    if not hasattr(container, "get_text"):
        return ""
    text = clean_text(container.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    if not match:
        return ""
    return re.sub(
        r"^现任(?:职务)?[：:]?\s*",
        "",
        clean_text(match.group(0)),
        count=1,
    )


def fetch_detail_evidence(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线读取详情页，核对姓名后返回完整现任职务原句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    name_node = soup.select_one(str(page_rule.get("detail_name_selector", "")))
    content_node = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if name_node is None or content_node is None:
        return ""
    if clean_name(name_node.get_text(" ", strip=True)) != expected_name:
        return ""
    return extract_current_sentence(content_node)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物目录顺序抓取各详情页的现任职务原句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = str(page_rule.get("detail_link_selector", ""))
    for source_order, link in enumerate(region.select(selector), start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            evidence = fetch_detail_evidence(detail_url, name, page_rule, source_order)
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
                    "strategy=custom_parse_page；list=ul.provincial-leaders-inner "
                    "dd.ldname a[istitle=true]；detail name=.xxgk_ldlxm；"
                    "current sentence=.xxgk_ldr scoped 现任[^。]*。"
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
