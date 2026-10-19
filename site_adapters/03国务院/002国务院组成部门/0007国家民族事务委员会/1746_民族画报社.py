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
    "rule_id": "1746", "page_type": "职务分组名单页", "structure_group": "mzhb_leadership_paragraph_colon_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_mzhb_leadership_paragraph_colon_v1",
    "leader_region_selector": "div.txt", "name_selector": "单位领导至内设部门之间p冒号后", "duty_selector": "单位领导至内设部门之间p冒号前", "detail_link_selector": "",
    "content_scope": {"start_anchor": "单位领导", "end_anchor": "内设部门", "include_selectors": ["div.txt"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "同一正文在单位领导之后继续列内设部门，必须按两个标题边界只解析中间职务姓名段落", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_heading_bounded_colon_paragraphs",
    "locator": {"css": {"region_selector": "div.txt", "row_selector": "p", "start_text": "单位领导", "end_text": "内设部门"}, "api": {"enabled": False, "reason": "原始HTML正文段落直接提供职务与姓名"}, "migration": {"source": "legacy_business_source_and_unverified_generic_parser_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    in_scope = False
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if text == "单位领导":
            in_scope = True
            continue
        if text == "内设部门":
            break
        if not in_scope:
            continue
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = clean_text(parts[0])
        name = clean_text(parts[1]).replace(" ", "")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=unit_leaders_to_departments；fields=paragraph_colon；order=dom"})
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
