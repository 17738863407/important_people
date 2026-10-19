from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.cicg.org.cn",
        "page_type": "人物列表完整页",
        "structure_group": "cicg_current_leader_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_heading_name_duty",
        "collector": "static_http",
        "parser": "page_cicg_current_leader_cards_v1",
        "leader_region_selector": ".Box1_List",
        "name_selector": ".Box1_List > dl > dd > h2",
        "duty_selector": ".Box1_List > dl > dd > h2",
        "detail_link_selector": "",
        "content_scope": {
            "start_anchor": "现任领导",
            "include_selectors": [".Box1_List"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "verified_heading_contains_exact_name_and_duty_without_detail_links",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".Box1_List",
                "item_selector": ":scope > dl",
                "heading_selector": ":scope > dd > h2",
            },
            "api": {"enabled": False, "reason": "静态HTML领导卡片已直接包含姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """限定现任领导区域，按卡片原始顺序拆分标题中的姓名与职务。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".Box1_List")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    heading_pattern = re.compile(r"^([\u3400-\u9fff·]{2,4})[（(](.+)[）)]$")
    for item in region.select(":scope > dl"):
        heading = item.select_one(":scope > dd > h2")
        if heading is None:
            continue
        match = heading_pattern.fullmatch(normalize_space(heading.get_text(" ", strip=True)))
        if match is None:
            continue
        name = match.group(1)
        duty = normalize_space(match.group(2)).strip(" ：:，,。.")
        if not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.Box1_List；"
                    "item=dl；field=dd>h2姓名（职务）；detail=none"
                ),
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        build_page_rule(rule_id),
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3562"
    main(rule_id_value)
