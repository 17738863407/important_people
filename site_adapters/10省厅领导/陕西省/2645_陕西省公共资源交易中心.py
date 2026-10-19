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
    "rule_id": "2645",
    "page_type": "职务分组名单页",
    "structure_group": "leader_navigation_to_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "ShaanxiPublicResourceLeaderDetailParser_v1",
    "leader_region_selector": ".wb-tree-sub a.wb-three-tt[href]",
    "name_selector": "导航链接冒号后文本",
    "duty_selector": ".ewb-leader-info中职务标签后一段",
    "detail_link_selector": ".wb-tree-sub a.wb-three-tt[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_name_selector": ".ewb-leader-name",
        "detail_duty_selector": ".ewb-leader-info职务标签后一段",
    },
    "confidence": "high",
    "risk_flag": "不得保留固定人员、职务及详情链接；详情职责段不得混入职务依据",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _extract_detail_duty(soup: BeautifulSoup) -> str:
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in soup.select(".ewb-leader-info p")]
    for index, text in enumerate(paragraphs[:-1]):
        if text.rstrip("：:") == "职务":
            return paragraphs[index + 1]
    return ""


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """保持左侧领导导航顺序，逐个从详情页提取姓名和职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".wb-tree-sub a.wb-three-tt[href]"):
        label = _clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"[：:]", label, maxsplit=1)
        if len(parts) != 2:
            continue
        list_name = _clean_name(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) or list_name in seen:
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        except Exception:
            continue
        detail_name_node = detail_soup.select_one(".ewb-leader-name")
        detail_name = _clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        duty = _extract_detail_duty(detail_soup)
        if detail_name != list_name or not duty:
            continue
        seen.add(list_name)
        verified_detail_url = "" if detail_result.final_url.rstrip("/") == base_url.rstrip("/") else detail_result.final_url
        records.append(
            {
                "name": list_name,
                "duty": "",
                "detail_url": verified_detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "列表=.wb-tree-sub a.wb-three-tt；详情姓名=.ewb-leader-name；职务=.ewb-leader-info职务标签后一段",
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
