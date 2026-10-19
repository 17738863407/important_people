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
    "rule_id": "0958", "page_type": "人物列表完整页", "structure_group": "hep_management_team_table_v2", "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_hep_management_team_table_v2",
    "leader_region_selector": "main table tr", "name_selector": "td:first-of-type", "duty_selector": "td:nth-of-type(2)", "detail_link_selector": "",
    "content_scope": {"start_anchor": "管理团队", "end_anchor": "高教站群", "include_selectors": ["main table"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "原始HTTP仅返回JavaScript壳页；当前浏览器DOM管理团队表格为权威来源", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_management_table",
    "locator": {"css": {"leader_region_selector": "main table tr", "name_selector": "td:first-of-type", "duty_selector": "td:nth-of-type(2)"}, "api": {"enabled": False, "reason": "当前渲染DOM管理团队表格直接提供姓名与职位"}, "migration": {"source": "legacy_offline_collector_business_source_and_old_table_class_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table_row in soup.select(page_rule["leader_region_selector"]):
        cells = table_row.select("td")
        if len(cells) < 2:
            continue
        name, duty = clean_text(cells[0].get_text(" ", strip=True)), clean_text(cells[1].get_text(" ", strip=True))
        if name in {"姓名", "姓名"} or duty in {"职位", "職位"}:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=main_management_table；name=col1；duty=col2；order=row"})
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
