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
    "rule_id": "0220", "page_type": "人物列表完整页", "structure_group": "china_language_about_leader_paragraphs_v2", "reuse_scope": "single_page", "load_mode": "接口数据加载", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_china_language_about_leader_paragraphs_v2",
    "leader_region_selector": ".ant-tabs-tabpane-active .aboutUs-view p", "name_selector": "colon_suffix_or_following_name_paragraph", "duty_selector": "所长_or_副所长_colon_prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "教育部", "include_selectors": [".ant-tabs-tabpane-active .aboutUs-view"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "前端应用渲染；副所长首人位于标题同行，其余副所长为后续姓名段落，限定当前激活领导介绍面板", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_active_tab_leader_paragraphs",
    "locator": {"css": {"leader_region_selector": ".ant-tabs-tabpane-active .aboutUs-view p", "row_pattern": "所长冒号姓名；副所长冒号首人+后续姓名段落"}, "api": {"enabled": False, "reason": "当前渲染DOM领导介绍面板直接提供姓名与职务分组"}, "migration": {"source": "legacy_fixed_old_people_business_source_and_entry_detail_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}

def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    lines = [compact(p.get_text(" ", strip=True)) for p in soup.select(page_rule["leader_region_selector"])]
    rows: list[dict[str, str]] = []
    deputy_started = False
    for line in lines:
        if not line or line == "领导介绍":
            continue
        match = re.fullmatch(r"所长[：:](?P<name>[\u4e00-\u9fff·]{2,10})", line)
        if match:
            rows.append({"name": match.group("name"), "duty": "所长", "detail_url": "", "source_text": "所长", "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=active_aboutUs；group=所长；order=dom"})
            continue
        match = re.fullmatch(r"副所长[：:](?P<name>[\u4e00-\u9fff·]{2,10})", line)
        if match:
            deputy_started = True
            rows.append({"name": match.group("name"), "duty": "副所长", "detail_url": "", "source_text": "副所长", "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=active_aboutUs；group=副所长；order=dom"})
            continue
        if deputy_started and re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", line):
            rows.append({"name": line, "duty": "副所长", "detail_url": "", "source_text": "副所长", "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=active_aboutUs；group=副所长；order=dom"})
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
