from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3435",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_planning_name_duty_headings_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_planning_name_duty_headings_v1",
    "leader_region_selector": "#zoom_1",
    "name_selector": "职务标题前姓名",
    "duty_selector": "党组职务标题",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#zoom_1"],
        "exclude_selectors": ["iframe", "script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "领导职务标题与工作分工连续排列；仅接受正文中明确党组职务标题",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_before_verified_duty_heading",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom_1",
            "name_selector": "han_name_before_verified_duty_heading",
            "duty_selector": "verified_party_group_duty_heading",
            "detail_link_selector": "",
        },
        "api": {"enabled": False, "reason": "原始HTML正文直接包含领导姓名、职务标题和分工"},
        "migration": {
            "source": "legacy_full_page_text_regex",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_DUTY_PATTERN = re.compile(
    r"(?<![\u4e00-\u9fff])"
    r"(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s+"
    r"(?P<duty>党组书记、局长|党组成员、驻局纪检组组长|党组成员、副局长)"
)


def clean_text(text: str) -> str:
    """将排版空白归一化，并保留标题与上一段之间的边界。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标题顺序解析姓名和原始党组职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(page_rule["leader_region_selector"])
    if content is None:
        return []
    text = clean_text(content.get_text(" ", strip=True))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in NAME_DUTY_PATTERN.finditer(text):
        name = re.sub(r"\s+", "", match.group("name"))
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "source_text": duty,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=zoom_1；heading=name_plus_verified_duty；work_division=excluded",
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
