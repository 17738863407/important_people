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
    "rule_id": "3999",
    "page_type": "现任领导人物卡片页",
    "structure_group": "tba_current_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "online",
    "parser": "custom_tba_current_leader_cards_v1",
    "leader_region_selector": ".hdld1bs1",
    "name_selector": ".hdld1bs1",
    "duty_selector": ".hdld1bs2",
    "detail_link_selector": "a[href][title]",
    "content_scope": {
        "start_anchor": "现任领导",
        "end_anchor": "沪ICP备",
        "include_selectors": [".hdld1bs1"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "dynamic_card_link"},
    "risk_flag": "普通HTTP受云防护拦截，需从浏览器渲染后的当前领导卡片读取。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验每个当前领导卡片内同时提供姓名、职务和独立详情链接。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".hdld1bs1",
            "name_selector": ".hdld1bs1",
            "duty_selector": ".hdld1bs2",
            "detail_link_selector": "a[href][title]",
        },
        "api": {"enabled": False, "reason": "渲染DOM卡片字段完整且与可见页面一致"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    """清理排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按当前领导卡片的DOM顺序提取姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for name_node in soup.select(".hdld1bs1"):
        link = name_node.find_parent("a", href=True, title=True)
        if link is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        duties = [
            clean_text(node.get_text(" ", strip=True))
            for node in link.select(".hdld1bs2")
        ]
        duties = [duty for duty in duties if duty]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duties:
            continue
        duty = "；".join(dict.fromkeys(duties))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, link.get("href", "")),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".hdld1bs1 姓名节点所属当前领导卡片",
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
