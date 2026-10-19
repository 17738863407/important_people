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
    "rule_id": "0744", "page_type": "人物列表完整页", "structure_group": "greenfood_leader_paragraphs_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_greenfood_leader_paragraphs_v2",
    "leader_region_selector": ".TRS_Editor p", "name_selector": "text before first duty marker", "duty_selector": "text from first duty marker", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".TRS_Editor"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "姓名含版面空格且多项职务以空格并列；仅清理排版空白，不添加或删除职务语义", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_name_duty_paragraphs",
    "locator": {"css": {"leader_region_selector": ".TRS_Editor p", "boundary": "first duty marker"}, "api": {"enabled": False, "reason": "当前原始HTML正文段落直接提供领导姓名和职务"}, "migration": {"source": "legacy_business_source_offline_dependency_and_semantic_rewrite_removed", "verified_status": "verified_current_raw_http", "behavior_changed": True}},
}


def normalize_space(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    duty_markers = ("党委书记", "纪委书记", "总工程师", "主任")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        line = normalize_space(paragraph.get_text(" ", strip=True))
        positions = [line.find(marker) for marker in duty_markers if line.find(marker) > 0]
        if not positions:
            continue
        boundary = min(positions)
        name = re.sub(r"\s+", "", line[:boundary])
        duty = normalize_space(line[boundary:])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=TRS_Editor_paragraph；boundary=first_duty_marker；order=paragraph_dom"})
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
