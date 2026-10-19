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


PAGE_RULE = {
    "rule_id": "1744",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_civil_affairs_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_civil_affairs_leader_cards_v1",
    "leader_region_selector": ".leader_list",
    "name_selector": ".leader_item .name",
    "duty_selector": ".leader_item .title",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": [".leader_list"],
        "exclude_selectors": [".leader_work", ".leader_resume"],
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
    "risk_flag": "同卡包含工作分工和个人简历长文本；仅读取.name和.title强字段，禁止使用整卡文本作为依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".leader_list .leader_item",
            "name_selector": ".name",
            "duty_selector": ".title",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": [".leader_list"],
                "exclude_selectors": ["工作分工区域", "个人简历区域"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导卡片直接包含明确姓名和职务强字段",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序读取姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".leader_list .leader_item"):
        name_node = item.select_one(".name")
        duty_node = item.select_one(".title")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_civil_affairs_leader_cards_v1",
                "selector_summary": ".leader_list .leader_item；name=.name；duty=.title",
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
