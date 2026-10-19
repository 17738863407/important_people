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
    "rule_id": "0174", "page_type": "人物表格页", "structure_group": "cdr_leader_editor_colon_rows_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cdr_leader_editor_colon_rows_v1",
    "leader_region_selector": "div.TRS_Editor > div", "name_selector": ":scope b", "duty_selector": "row_text_after_colon", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": ["div.TRS_Editor"], "exclude_selectors": ["iframe", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "页面带空src跳转iframe但领导信息已在主HTML TRS_Editor直出；姓名含排版空格，另有空行", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_editor_colon_rows",
    "locator": {"css": {"leader_region_selector": "div.TRS_Editor > div", "name_selector": ":scope b", "duty_boundary": "colon"}, "api": {"enabled": False, "reason": "原始HTML编辑器区域直接提供姓名和职务"}, "migration": {"source": "legacy_offline_claim_and_unused_detail_parser_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for row in soup.select(page_rule["leader_region_selector"]):
        label = row.select_one("b")
        line = clean_text(row.get_text(" ", strip=True))
        parts = re.split(r"[：:]", line, maxsplit=1)
        name = clean_text(label.get_text(" ", strip=True) if label else "").rstrip("：:").replace(" ", "")
        duty = clean_text(parts[1]) if len(parts) == 2 else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=trs_editor；fields=bold_name_colon_duty；order=dom"})
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
