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
    "rule_id": "3422",
    "domain": "zscq.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_cards_detail_first_role_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_cards_detail_first_role_sentence_v1",
    "leader_region_selector": "ul.mod_more_content_ul_img",
    "detail_link_selector": "p.mod_more_content_title_img a[href]",
    "detail_content_selector": "#content",
    "detail_strategy": {"required": True, "mode": "list_to_detail_first_role_sentence"},
    "risk_flag": "每人同时有图片与标题链接；仅取标题卡片，详情首句后工作分工必须排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩详情文本中的排版空白，不改变原句标点和语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail_evidence(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线读取详情页，以标题核名后返回首个本人职务句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    title = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    content_node = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if title != expected_name or content_node is None:
        return ""
    text = clean_text(content_node.get_text(" ", strip=True))
    match = re.match(rf"{re.escape(expected_name)}\s*[，,]\s*[^。]*。", text)
    if not match or "辽宁省知识产权局" not in match.group(0):
        return ""
    evidence = clean_text(match.group(0))
    evidence = re.sub(rf"^{re.escape(expected_name)}\s*[，,]\s*", "", evidence)
    return evidence.rstrip("。").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口标题卡片顺序抓取各详情页首个本人职务句。"""
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
                    "strategy=custom_parse_page；list=ul.mod_more_content_ul_img "
                    "p.mod_more_content_title_img a；detail name=title；"
                    "evidence=#content first 本人，辽宁省知识产权局...。"
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
