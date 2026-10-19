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
    "rule_id": "2646",
    "page_type": "人物列表完整页",
    "structure_group": "leader_list_to_biography_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "ShaanxiSupplyLeaderDetailParser_v1",
    "leader_region_selector": "a.clearfix[href]",
    "name_selector": ".text",
    "duty_selector": ".article-content内完整现任句",
    "detail_link_selector": "a.clearfix[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_name_selector": ".public-title-nav .title",
        "detail_content_selector": ".article-content",
    },
    "confidence": "high",
    "risk_flag": "职务仅在人物详情简介中，必须限定当前人物正文并保留完整现任句；禁止本地详情快照",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """保持省社领导列表顺序，逐个从详情正文提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a.clearfix[href]"):
        name_node = link.select_one(".text")
        list_name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) or list_name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        except Exception:
            continue
        detail_name_node = detail_soup.select_one(".public-title-nav .title")
        content_node = detail_soup.select_one(".article-content")
        detail_name = _clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        content = _clean_text(content_node.get_text(" ", strip=True) if content_node else "")
        current_match = re.search(r"现任[^。]*。", content)
        if detail_name != list_name or current_match is None:
            continue
        seen.add(list_name)
        records.append(
            {
                "name": list_name,
                "duty": "",
                "detail_url": detail_result.final_url,
                "evidence": _clean_current_evidence(current_match.group(0)),
                "parser": rule["parser"],
                "selector_summary": "列表=a.clearfix .text；详情姓名=.public-title-nav .title；依据=.article-content内完整现任句",
                "order": str(len(records) + 1),
            }
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
