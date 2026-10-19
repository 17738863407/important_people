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
    "rule_id": "0354", "page_type": "人物列表完整页", "structure_group": "cttic_leader_paragraph_pairs_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cttic_leader_paragraph_pairs_v2",
    "leader_region_selector": "div.zxjs-1[style*='750px'] p", "name_selector": "name_paragraph", "duty_selector": "next_nonempty_paragraph", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "Copyright", "include_selectors": ["div.zxjs-1[style*='750px']"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "姓名与职务为相邻非空段落且夹有空段落；完整职务含机构前缀，必须原样保留而不做语义删减", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_nonempty_paragraph_pairs",
    "locator": {"css": {"leader_region_selector": "div.zxjs-1[style*='750px'] p", "row_pattern": "姓名段落+下一非空完整职务段落"}, "api": {"enabled": False, "reason": "原始HTML领导介绍正文直接提供姓名与职务相邻段落"}, "migration": {"source": "legacy_business_source_and_duty_prefix_removal_deleted", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()
    text = re.sub(r"\s*([、，；：])\s*", r"\1", text)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(page_rule["leader_region_selector"])]
    paragraphs = [text for text in paragraphs if text]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    index = 0
    while index + 1 < len(paragraphs):
        name = paragraphs[index].replace(" ", "")
        duty = paragraphs[index + 1]
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty and name not in seen:
            seen.add(name)
            rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=zxjs_750px；pair=name_then_next_nonempty_duty；order=dom"})
            index += 2
            continue
        index += 1
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
