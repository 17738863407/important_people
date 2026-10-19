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
    "rule_id": "0153", "page_type": "人物列表完整页", "structure_group": "ccs_executive_paragraph_name_duty_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ccs_executive_paragraph_name_duty_v1",
    "leader_region_selector": "div.ccrj.mb_85 div.p p.MsoNormal", "name_selector": "paragraph_leading_name", "duty_selector": "paragraph_trailing_executive_title", "detail_link_selector": "",
    "content_scope": {"start_anchor": "CCS高层", "end_anchor": "Copyright", "include_selectors": ["div.ccrj.mb_85 div.p"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "正文含空段落且二字姓名带排版空格，限定CCS高层正文并要求职务含总裁、书记或委员标题", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_executive_paragraph_regex",
    "locator": {"css": {"leader_region_selector": "div.ccrj.mb_85 div.p p.MsoNormal", "row_pattern": "段首2至4字姓名+高层职务"}, "api": {"enabled": False, "reason": "原始HTML高层正文段落直接提供姓名和完整职务"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        line = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]\s*[\u4e00-\u9fff·]{1,3})\s+(?P<duty>.+(?:总裁|书记|委员).*)", line)
        if match is None:
            continue
        name = match.group("name").replace(" ", "")
        duty = clean_text(match.group("duty"))
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=ccrj_mb85；boundary=leading_name_and_executive_title；order=dom"})
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
