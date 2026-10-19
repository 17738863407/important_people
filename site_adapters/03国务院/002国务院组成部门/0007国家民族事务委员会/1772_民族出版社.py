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
    "rule_id": "1772", "page_type": "人物列表完整页", "structure_group": "mzpub_management_team_table_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_mzpub_management_team_table_v1",
    "leader_region_selector": "table", "name_selector": "tr td:nth-of-type(3)", "duty_selector": "tr td:nth-of-type(2)", "detail_link_selector": "",
    "content_scope": {"start_anchor": "管理团队", "end_anchor": "内设机构", "include_selectors": ["table"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "页面含管理团队和内设机构多个表格；仅选择包含党委书记、社长字段的团队表，按第二、三单元格解析", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_identified_management_table",
    "locator": {"css": {"table_selector": "table", "row_selector": "tr", "duty_cell_index": 1, "name_cell_index": 2}, "api": {"enabled": False, "reason": "原始HTML管理团队表格直接提供职务和姓名"}, "migration": {"source": "legacy_business_source_personrecord_and_entry_detail_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    table = next((node for node in soup.select(page_rule["leader_region_selector"]) if "党委书记、社长" in clean_text(node.get_text(" ", strip=True))), None)
    if table is None:
        return []
    rows: list[dict[str, str]] = []
    for row in table.select("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.select("td")]
        if len(cells) < 3:
            continue
        duty = cells[1]
        name = cells[2].replace(" ", "")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=management_team_table；fields=td_2_td_3；order=table_row"})
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
