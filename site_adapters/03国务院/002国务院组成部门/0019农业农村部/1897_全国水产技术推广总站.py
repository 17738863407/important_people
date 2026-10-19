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
    "rule_id": "1897", "page_type": "人物列表完整页", "structure_group": "nftec_alternating_paragraphs_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_nftec_alternating_paragraphs_v2",
    "leader_region_selector": ".TRS_Editor p", "name_selector": "nonempty odd paragraph", "duty_selector": "following nonempty paragraph", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".TRS_Editor"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "领导正文为姓名与职务交替非空段落；仅在TRS_Editor内按网页顺序成对解析", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_alternating_paragraphs",
    "locator": {"css": {"leader_region_selector": ".TRS_Editor p", "row_pattern": "alternating nonempty name and duty"}, "api": {"enabled": False, "reason": "当前原始HTML正文直接提供交替姓名职务段落"}, "migration": {"source": "legacy_business_source_and_offline_dependency_removed", "verified_status": "verified_current_raw_http", "behavior_changed": True}},
}

def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    texts = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(page_rule["leader_region_selector"])]
    texts = [text for text in texts if text]
    rows: list[dict[str, str]] = []
    for index in range(0, len(texts) - 1, 2):
        name, duty = texts[index].replace(" ", ""), texts[index + 1]
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=TRS_Editor；order=alternating_paragraph_dom"})
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
