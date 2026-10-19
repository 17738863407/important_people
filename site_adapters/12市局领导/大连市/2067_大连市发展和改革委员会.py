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
    "rule_id": "2067",
    "page_type": "人物列表完整页",
    "structure_group": "dalian_drc_leader_list_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "leader_region_selector": "#zp_list .zfxxgk_zdgkc",
    "detail_link_selector": "a.text-tag[href*='/art/'][href*='art_8899']",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_content_selector": "div.art_con",
        "max_detail_links": 30,
    },
    "risk_flag": "详情正文首段为职务，后续段落为主持、负责等分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def extract_detail_duty(detail_html: str) -> str:
    """只取详情正文第一个非空段落作为原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("div.art_con")
    if content is None:
        return ""
    for paragraph in content.select("p"):
        text = paragraph.get_text(" ", strip=True)
        if text:
            return text
    return ""


def clean_evidence(value: str) -> str:
    """移除固定职务标签和纯句末标点，保留原始职务。"""
    text = re.sub(r"^(?:职务|现任职务|现任)[：:]?", "", str(value or "").strip())
    return text.rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口页 DOM 顺序遍历人物详情页并提取职务首段。"""
    from crawler_core.fetcher import fetch_by_requests

    soup = BeautifulSoup(html, "html.parser")
    selector = str(page_rule.get("detail_link_selector") or "")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for order, link in enumerate(soup.select(f"#zp_list .zfxxgk_zdgkc {selector}"), start=1):
        name = "".join(link.get_text(" ", strip=True).split())
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not name or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_by_requests(detail_url)
        duty = clean_evidence(extract_detail_duty(detail_result.html))
        if not duty:
            raise RuntimeError(f"详情页未找到职务首段：{detail_result.final_url}")
        rows.append(
            {
                "order": str(order),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_dalian_drc_leader_list_detail_v1",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
