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
    "rule_id": "0331", "page_type": "人物列表完整页", "structure_group": "crtdc_leader_table_cells_v2", "reuse_scope": "single_page", "load_mode": "接口数据加载", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_crtdc_leader_table_cells_v2",
    "leader_region_selector": "main table td", "name_selector": "cell_prefix_name", "duty_selector": "cell_suffix_duty", "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "版权所有", "include_selectors": ["main table"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "原始HTTP仅为数据加载壳页；限定当前中心领导表格，单元格为姓名空格职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_table_cell_name_duty",
    "locator": {"css": {"leader_region_selector": "main table td", "row_pattern": "姓名+职务"}, "api": {"enabled": False, "reason": "当前渲染DOM中心领导表格直接提供姓名与职务"}, "migration": {"source": "legacy_offline_business_source_and_entry_detail_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for cell in soup.select(page_rule["leader_region_selector"]):
        text = clean_text(cell.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,10})\s+(?P<duty>.+)", text)
        if match:
            rows.append({"name": match.group("name"), "duty": match.group("duty"), "detail_url": "", "source_text": match.group("duty"), "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=main_leader_table；boundary=first_space；order=row_cell"})
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
