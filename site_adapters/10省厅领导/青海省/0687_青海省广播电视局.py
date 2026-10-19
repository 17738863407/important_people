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
    """规范化页面文本空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def split_duty_name(value: str) -> tuple[str, str] | None:
    """拆分卡片标题中的“职务 姓名”。"""
    match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,8})", clean_text(value))
    if match is None:
        return None
    return clean_text(match.group(1)), match.group(2)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片的页面顺序提取明确标题字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("#GDJ_Leader_Group .GDJ_Leader_Box_A"):
        title = card.select_one("h3")
        parsed = split_duty_name(title.get_text(" ", strip=True) if title else "")
        if parsed is None:
            continue
        duty, name = parsed
        if name in seen:
            continue
        seen.add(name)
        link = card.select_one("a[href]")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_gdj_cards_v2",
                "selector_summary": "leader=#GDJ_Leader_Group .GDJ_Leader_Box_A；name/duty=h3；detail=card a[href]",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0687",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_gdj_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_gdj_cards_v2",
    "leader_region_selector": "#GDJ_Leader_Group .GDJ_Leader_Box_A",
    "name_selector": "h3末尾姓名",
    "duty_selector": "h3姓名前职务",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#GDJ_Leader_Group"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
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
            "leader_region_selector": "#GDJ_Leader_Group .GDJ_Leader_Box_A",
            "name_selector": "h3末尾姓名",
            "duty_selector": "h3姓名前职务",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["#GDJ_Leader_Group"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML已直接提供完整领导卡片"},
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
