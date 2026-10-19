from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "2805",
    "page_type": "人物列表完整页",
    "structure_group": "xining_veterans_affairs_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xining_veterans_affairs_leader_cards_v1",
    "leader_region_selector": ".fdzdjg-content-box-content.box1-content",
    "name_selector": ".name",
    "duty_selector": ".position",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".fdzdjg-content-box-content.box1-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "领导卡片位于机关简介页的领导信息区域；仅提取该区域内可见人物卡片",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先上明确隐藏的人物卡片。"""
    for current in [node, *node.parents]:
        if not isinstance(current, Tag):
            continue
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if (
            current.has_attr("hidden")
            or str(current.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide"})
        ):
            return True
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导信息区域的人物卡片顺序逐卡提取强字段。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in region.select(".person"):
        if _is_hidden(card):
            continue
        name_node = card.select_one(str(page_rule.get("name_selector") or ""))
        duty_node = card.select_one(str(page_rule.get("duty_selector") or ""))
        name = "".join((name_node.get_text(" ", strip=True) if name_node else "").split())
        duty = " ".join((duty_node.get_text(" ", strip=True) if duty_node else "").split())
        if not name or not duty or name in seen:
            continue
        link = card.select_one(str(page_rule.get("detail_link_selector") or ""))
        detail_url = urljoin(final_url, str(link.get("href", ""))) if link else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": (
                    ".fdzdjg-content-box-content.box1-content内.person；"
                    ".name=姓名；.position=依据；当前卡片a[href]=详情页"
                ),
            }
        )
    return rows


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
