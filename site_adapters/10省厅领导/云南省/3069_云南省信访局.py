from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3069",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_petition_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_petition_leader_cards_v2",
    "leader_region_selector": "a.leader-item",
    "name_selector": ".name",
    "duty_selector": ".post",
    "detail_link_selector": "a.leader-item[href]",
    "content_scope": {
        "start_anchor": "首张领导卡片",
        "end_anchor": "末张领导卡片",
        "include_selectors": ["a.leader-item"],
        "exclude_selectors": ["机构职能", "内设机构", "通知公告", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a.leader-item[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "职务节点由多个HTML分行组成；仅做排版空白归一，不添加机构前缀或标点",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "a.leader-item",
            "name_selector": ".name",
            "duty_selector": ".post",
            "detail_link_selector": "a.leader-item[href]",
            "content_scope": {
                "start_anchor": "首张领导卡片",
                "end_anchor": "末张领导卡片",
                "include_selectors": ["a.leader-item"],
                "exclude_selectors": ["机构职能", "内设机构", "通知公告", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML领导卡片直接提供姓名、职务和详情链接"},
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
        if "leader-item" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("a.leader-item"):
        if _is_hidden(card):
            continue
        name_node = card.select_one(".name")
        duty_node = card.select_one(".post")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。.；;")
        href = str(card.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_yunnan_petition_leader_cards_v2",
                "selector_summary": "a.leader-item；.name姓名；.post完整职务；卡片href详情",
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
