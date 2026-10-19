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


def clean_text(value: str) -> str:
    """压缩Word表格正文排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按Word表格行顺序提取姓名和完整现任职务原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in soup.select(".trs_word_table tr"):
        text = clean_text(table_row.get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})[，,]", text)
        duty_match = re.search(r"(?P<evidence>现任[^。]*。)", text)
        if name_match is None or duty_match is None or name_match.group("name") in seen:
            continue
        name, evidence = name_match.group("name"), duty_match.group("evidence").removeprefix("现任").strip().removesuffix("。")
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_approval_word_table_v2",
                     "selector_summary": "leader=.trs_word_table tr；name=text before first comma；duty=complete current-duty sentence；detail=none"})
    return rows


PAGE_RULE = {
    "rule_id": "3104", "page_type": "人物表格页", "structure_group": "shanxi_approval_word_table", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_approval_word_table_v2",
    "leader_region_selector": ".trs_word_table tr", "name_selector": "row text before first comma", "duty_selector": "row complete current-duty sentence", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_word_table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "raw_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "每行同时含履历、现任职务和主持/分管/负责内容，只提取完整现任句", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".trs_word_table tr", "name_selector": "row text before first comma", "duty_selector": "row complete current-duty sentence", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".trs_word_table"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML Word表格已直出姓名和完整现任职务句"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
