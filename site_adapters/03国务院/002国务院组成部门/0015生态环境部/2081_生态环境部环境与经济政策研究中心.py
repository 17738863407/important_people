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
    "rule_id": "2081",
    "domain": "www.prcee.org",
    "page_type": "人物列表完整页",
    "structure_group": "prcee_main_current_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_prcee_current_leaders_v1",
    "leader_region_selector": "div.main #right .menu_list",
    "name_selector": ".pic_box .txt span",
    "duty_selector": ".pic_box .txt > a",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "现任领导",
        "end_anchor": "",
        "include_selectors": ["div.main #right .menu_list .pic_box"],
        "exclude_selectors": [".nav_div"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "导航下拉区复制同一人物卡片；主内容旧详情URL仅存在HTML注释，不得作为详情页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.main #right .menu_list",
            "name_selector": ".pic_box .txt span",
            "duty_selector": ".pic_box .txt > a",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "现任领导",
                "end_anchor": "",
                "include_selectors": ["div.main #right .menu_list .pic_box"],
                "exclude_selectors": [".nav_div"],
            },
        },
        "api": {"enabled": False, "reason": "当前主内容HTML已静态直出姓名和职务字段"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白及中文标点周边空格。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ").replace("\u2003", " ")).strip()
    text = re.sub(r"\s+([，、；。])", r"\1", text)
    return re.sub(r"([，、；。])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按主内容现任领导卡片DOM顺序抽取姓名和职务。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=div.main #right .menu_list；item=.pic_box；exclude=.nav_div"

    for card in soup.select("div.main #right .menu_list .pic_box"):
        name_node = card.select_one(".txt span")
        duty_node = card.select_one(".txt > a")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
