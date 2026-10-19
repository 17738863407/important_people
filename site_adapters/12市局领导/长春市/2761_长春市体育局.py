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


PAGE_RULE = {
    "rule_id": "2761",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_sports_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_sports_leader_cards_v1",
    "leader_region_selector": "div.tyjgk_jj > ul > li > a[href]",
    "name_selector": ":scope > span",
    "duty_selector": ":scope > p",
    "detail_link_selector": "div.tyjgk_jj > ul > li > a[href]",
    "content_scope": {
        "start_anchor": "长春市体育局领导简介",
        "end_anchor": "",
        "include_selectors": ["div.tyjgk_jj > ul"],
        "exclude_selectors": ["header", "footer", "nav"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_link_from_card",
        "detail_collector_type": "static_http",
        "detail_link_selector": "div.tyjgk_jj > ul > li > a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "领导卡片同时含头像、职务和姓名；仅取卡片直属p和span强字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_card_name_duty_detail",
    "locator": {
        "css": {
            "leader_region_selector": "div.tyjgk_jj > ul > li > a[href]",
            "name_selector": ":scope > span",
            "duty_selector": ":scope > p",
            "detail_link_selector": "same_anchor_href",
        },
        "api": {
            "enabled": False,
            "reason": "静态人物卡片已直接提供姓名、职务和独立简介链接",
        },
        "migration": {
            "source": "legacy_card_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")


def clean_text(text: str) -> str:
    """压缩HTML排版空白，不改变网页文字语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取姓名、职务和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select(page_rule["leader_region_selector"]):
        name_node = anchor.find("span", recursive=False)
        duty_node = anchor.find("p", recursive=False)
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if NAME_PATTERN.fullmatch(name) is None or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": urljoin(final_url, str(anchor.get("href") or "").strip()),
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=tyjgk_jj_direct_cards；name=direct_span；duty=direct_p；detail=same_anchor_href",
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
