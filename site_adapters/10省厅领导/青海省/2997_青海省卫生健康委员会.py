from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理HTML字段排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按移动版领导卡片顺序提取独立姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".qw-leader-list a.a.clearfix[href]"):
        name_node = card.select_one("p.title")
        duty_node = card.select_one("p.tt")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(card.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_health_cards_v2",
                "selector_summary": "leader=.qw-leader-list a.a.clearfix[href]；name=p.title；duty=p.tt；detail=href",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2997",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_health_mobile_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_health_cards_v2",
    "leader_region_selector": ".qw-leader-list a.a.clearfix[href]",
    "name_selector": "p.title",
    "duty_selector": "p.tt",
    "detail_link_selector": ".qw-leader-list a.a.clearfix[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".qw-leader-list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": ".qw-leader-list a.a.clearfix[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".qw-leader-list a.a.clearfix[href]",
            "name_selector": "p.title",
            "duty_selector": "p.tt",
            "detail_link_selector": ".qw-leader-list a.a.clearfix[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".qw-leader-list"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "移动版静态HTML已直出完整领导卡片"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
