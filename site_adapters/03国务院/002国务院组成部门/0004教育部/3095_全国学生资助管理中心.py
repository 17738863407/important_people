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
    "rule_id": "3095", "page_type": "人物列表完整页", "structure_group": "xszz_leader_name_duty_paragraphs_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_xszz_leader_name_duty_paragraphs_v1",
    "leader_region_selector": ".article p", "name_selector": "paragraph_prefix_before_duty", "duty_selector": "recognized_duty_suffix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "Copyright", "include_selectors": [".article"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "姓名字符间含多个不换行空格；限定领导正文段落并按完整职务后缀拆分", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_paragraph_duty_suffix",
    "locator": {"css": {"leader_region_selector": ".article p", "row_pattern": "姓名+党委书记主任/副主任/党委副书记纪委书记"}, "api": {"enabled": False, "reason": "原始HTML领导正文段落直接提供姓名与职务"}, "migration": {"source": "legacy_business_source_and_stale_metadata_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}

def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    duties = ("党委副书记、纪委书记", "党委书记、主任", "副主任")
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        line = compact(paragraph.get_text(" ", strip=True))
        duty = next((item for item in duties if line.endswith(item)), "")
        name = line[:-len(duty)] if duty else ""
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=article；boundary=duty_suffix；order=dom"})
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
