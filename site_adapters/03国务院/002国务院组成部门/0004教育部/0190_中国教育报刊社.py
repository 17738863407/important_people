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
    "rule_id": "0190", "page_type": "现任领导名单页", "structure_group": "cepa_current_leader_adjacent_lines_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cepa_current_leader_adjacent_lines_v1",
    "leader_region_selector": "#pageECt", "name_selector": "odd_nonempty_line_after_heading", "duty_selector": "next_nonempty_line", "detail_link_selector": "",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "Copyright", "include_selectors": ["#pageECt"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "限定pageECt现任领导区，标题后按姓名与下一非空职务行配对", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_adjacent_lines",
    "locator": {"css": {"leader_region_selector": "#pageECt", "row_pattern": "现任领导标题后姓名行+职务行"}, "api": {"enabled": False, "reason": "原始HTML现任领导区直接包含完整姓名职务行"}, "migration": {"source": "legacy_business_source_entry_detail_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []
    lines = [compact(line) for line in region.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line and line != "现任领导"]
    rows: list[dict[str, str]] = []
    for index in range(0, len(lines) - 1, 2):
        name, duty = lines[index], lines[index + 1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=pageECt；pair=name_then_duty；order=dom_lines"})
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
