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
    """压缩表格排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导信息表格顺序读取首行姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in soup.select("table.ldxx"):
        first_row = table.select_one("tr")
        text = clean_text(first_row.get_text(" ", strip=True) if first_row else "")
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+)$", text)
        if match is None or match.group("name") in seen:
            continue
        name, evidence = match.group("name"), clean_text(match.group("duty"))
        if not re.search(r"书记|局长|党组|巡视员", evidence):
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_petitions_tables_v2",
                     "selector_summary": "leader=table.ldxx；name=first-row first token；duty=first-row remaining text；detail=none"})
    return rows


PAGE_RULE = {
    "rule_id": "3065", "page_type": "人物表格页", "structure_group": "shanxi_petitions_leader_tables", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_petitions_tables_v2",
    "leader_region_selector": "table.ldxx", "name_selector": "tr:first-child first token", "duty_selector": "tr:first-child remaining text", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "以上信息更新于", "include_selectors": ["table.ldxx"], "exclude_selectors": [".content"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "raw_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "每个领导表格第二行含履历、现任句和分管信息，只读取首行强结构姓名职务", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "table.ldxx", "name_selector": "tr:first-child first token", "duty_selector": "tr:first-child remaining text", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "以上信息更新于", "include_selectors": ["table.ldxx"], "exclude_selectors": [".content"]}}, "api": {"enabled": False, "reason": "静态HTML领导表格首行已直出姓名和职务"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
