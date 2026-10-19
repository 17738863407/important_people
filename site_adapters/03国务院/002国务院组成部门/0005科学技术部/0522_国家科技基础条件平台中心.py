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
    "rule_id": "0522", "page_type": "职务分组名单页", "structure_group": "escience_nsti_leader_table_v2", "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_escience_nsti_leader_table_v2",
    "leader_region_selector": "table tr", "name_selector": "colon_suffix_split_dunhao", "duty_selector": "colon_prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "机构设置", "include_selectors": ["table"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "原始HTML无中心领导表格；当前渲染DOM表格行由拆分单元格组成，合并行文本后按冒号和顿号解析", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_grouped_table_rows",
    "locator": {"css": {"leader_region_selector": "table tr", "row_pattern": "主任/副主任：姓名顿号列表"}, "api": {"enabled": False, "reason": "当前渲染DOM中心领导表格直接提供职务分组名单"}, "migration": {"source": "legacy_offline_business_source_and_invalid_natural_language_selector_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}

def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table_row in soup.select(page_rule["leader_region_selector"]):
        line = compact(table_row.get_text("", strip=True)).replace(":", "：", 1)
        match = re.fullmatch(r"(?P<duty>主任|副主任)：(?P<names>.+)", line)
        if match is None:
            continue
        duty = match.group("duty")
        for raw_name in re.split(r"[、，,]", match.group("names")):
            name = compact(raw_name)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
                rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=nsti_leader_table；boundary=colon_and_dunhao；order=row_then_name"})
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
