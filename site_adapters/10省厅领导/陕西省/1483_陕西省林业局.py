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
    "rule_id": "1483",
    "page_type": "人物列表完整页",
    "structure_group": "leader_list_to_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "ShaanxiForestryLeaderDetailParser_v1",
    "leader_region_selector": ".ld-list-ul .img-boxlf",
    "name_selector": ".name",
    "duty_selector": ".ldzc-zw",
    "detail_link_selector": ".ld-list-ul .img-boxlf a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_name_selector": ".ldzc-title",
        "detail_duty_selector": ".ldzc-zw",
    },
    "confidence": "high",
    "risk_flag": "列表页仅直出姓名，职务必须从当前动态详情页取得；不得保留固定姓名职务表",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """保持列表顺序，逐个从人物详情页取得当前职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".ld-list-ul .img-boxlf"):
        name_node = card.select_one(".name")
        link_node = card.select_one("a[href]")
        if name_node is None or link_node is None:
            continue
        list_name = _clean_name(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) or list_name in seen:
            continue

        detail_url = urljoin(base_url, link_node.get("href", ""))
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        except Exception:
            continue

        detail_name_node = detail_soup.select_one(".ldzc-title")
        duty_node = detail_soup.select_one(".ldzc-zw")
        detail_name = _clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if detail_name != list_name or not duty:
            continue

        seen.add(list_name)
        records.append(
            {
                "name": list_name,
                "duty": "",
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "列表=.ld-list-ul .img-boxlf；姓名=.name；详情姓名=.ldzc-title；详情职务=.ldzc-zw",
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
