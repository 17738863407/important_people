from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2749",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_statistics_leader_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_statistics_leader_blocks_v1",
    "leader_region_selector": "div.ldy_p",
    "name_selector": "div.ldy_p h3 span.blue",
    "duty_selector": "div.ldy_p h3",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个领导块",
        "end_anchor": "末个领导块",
        "include_selectors": ["div.ldy_p h3"],
        "exclude_selectors": ["分工段", "简历段", "隐藏节点"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "领导块同时含分工和简历；只使用h3中的span.blue姓名及其后职务文本",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.ldy_p",
            "name_selector": "h3 span.blue",
            "duty_selector": "h3中姓名节点后的文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个领导块",
                "end_anchor": "末个领导块",
                "include_selectors": ["div.ldy_p h3"],
                "exclude_selectors": ["分工段", "简历段", "隐藏节点"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML领导块h3直接提供姓名和职务，页面无人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "ldy_p" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("div.ldy_p"):
        if _is_hidden(card):
            continue
        title = card.select_one("h3")
        name_node = title.select_one("span.blue") if title is not None else None
        if title is None or name_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        title_text = _clean_text(title.get_text(" ", strip=True))
        duty = title_text[len(name) :].strip() if title_text.startswith(name) else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_xinjiang_statistics_leader_blocks_v1",
                "selector_summary": "div.ldy_p；h3 span.blue姓名；h3剩余文本职务",
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
