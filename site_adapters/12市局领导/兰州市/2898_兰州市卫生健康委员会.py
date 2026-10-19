from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2898",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_health_leader_cards_summary_heads_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_health_leader_cards_summary_heads_v1",
    "leader_region_selector": "ul.list_title",
    "name_selector": "li.leaderName-item a.leaderName-title span",
    "duty_selector": "li.leaderName-item p.leaderName-bref首个句号或冒号前的原始职务头",
    "detail_link_selector": "li.leaderName-item a.leaderName-title[href]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
        "detail_link_selector": "li.leaderName-item a.leaderName-title[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "summary_heads_mix_duty_and_name_while_following_text_is_responsibility",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.list_title",
            "row_selector": "li.leaderName-item",
            "name_selector": "a.leaderName-title span",
            "summary_selector": "p.leaderName-bref",
            "detail_link_selector": "a.leaderName-title[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线领导专栏直出8个人物卡片及真实详情链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按卡片DOM顺序提取姓名、职务头原文和动态详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ul.list_title")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select("li.leaderName-item"):
        link = item.select_one("a.leaderName-title[href]")
        name_node = item.select_one("a.leaderName-title span")
        summary_node = item.select_one("p.leaderName-bref")
        if link is None or name_node is None or summary_node is None:
            continue
        name = re.sub(r"\s+", "", normalize_space(name_node.get_text(" ", strip=True)))
        summary = normalize_space(summary_node.get_text(" ", strip=True))
        head_match = re.match(r"(?P<head>.+?)(?P<delimiter>[。：:])", summary)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not head_match
            or name in seen_names
        ):
            continue
        evidence = re.sub(r"[（(]挂职[）)]", "", head_match.group("head"))
        if evidence.endswith(name):
            evidence = evidence[: -len(name)]
        evidence = evidence.strip("，、；：:. ")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "ul.list_title内leaderName-item卡片顺序；span姓名；leaderName-bref第一个句号/冒号之前的原始职务头；卡片真实链接",
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
