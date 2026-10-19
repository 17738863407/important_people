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
    "rule_id": "2069", "page_type": "人物列表完整页", "structure_group": "pep_management_table_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_pep_management_table_v2",
    "leader_region_selector": "table tr", "name_selector": "td:nth-of-type(2) h3 first_text_before_br", "duty_selector": "td:first-of-type", "detail_link_selector": "",
    "content_scope": {"start_anchor": "管理团队", "end_anchor": "Copyright", "include_selectors": ["table"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "部分姓名单元格在姓名后含翻译/搜索/复制辅助文本，只读取h3首个文本节点", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_management_table_first_text_name",
    "locator": {"css": {"leader_region_selector": "table tr", "duty_selector": "td:first-of-type", "name_selector": "td:nth-of-type(2) h3首文本"}, "api": {"enabled": False, "reason": "原始HTML管理团队表格直接提供职位和姓名"}, "migration": {"source": "legacy_fixed_people_list_business_source_and_full_page_text_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table_row in soup.select(page_rule["leader_region_selector"]):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        duty = clean_text(cells[0].get_text(" ", strip=True))
        name_root = cells[1].select_one("h3") or cells[1]
        first_text = next((str(node) for node in name_root.children if isinstance(node, str) and clean_text(str(node))), "")
        name = clean_text(first_text).replace(" ", "")
        if name == "姓名" or duty == "职务":
            continue
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=management_table；duty=col1；name=col2_h3_first_text；order=row"})
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
