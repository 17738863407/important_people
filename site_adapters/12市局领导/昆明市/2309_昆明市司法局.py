from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2309",
    "page_type": "人物目录详情页",
    "structure_group": "kunming_justice_directory_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_justice_directory_details_v1",
    "leader_region_selector": ".right .leadership-list-data",
    "name_selector": "a p",
    "duty_selector": "动态详情页.right内完整现任句",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": ".right .leadership-list-data a[href]",
        "detail_content_selector": ".right",
        "max_detail_links": 20,
    },
    "risk_flag": "directory_names_require_dynamic_detail_fetch",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "cards": ".right .leadership-list-data a[href]",
            "name": "p",
            "detail_content": ".right",
            "detail_evidence": "current-position sentence",
        },
        "api": {
            "enabled": False,
            "reason": "目录页动态提供人物详情链接，详情页正文直接包含完整现任句",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序动态抓取人物详情，并从当前人物正文提取现任原句。"""
    from crawler_core.fetcher import fetch_online_html

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in soup.select(".right .leadership-list-data a[href]"):
        name_node = card.select_one("p")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", normalize_space(name_node.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(card.get("href", "")).strip())
        try:
            detail_html, resolved_url = fetch_online_html(detail_url)
        except Exception:
            continue
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_region = detail_soup.select_one(".right")
        if detail_region is None:
            continue
        detail_text = normalize_space(detail_region.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None or name not in re.sub(r"\s+", "", detail_text):
            continue
        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": resolved_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "目录人物卡片；动态详情.right；完整现任句",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
