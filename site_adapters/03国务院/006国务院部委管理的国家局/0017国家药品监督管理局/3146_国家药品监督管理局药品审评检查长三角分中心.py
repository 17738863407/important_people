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
    "rule_id": "3146", "page_type": "人物列表完整页", "structure_group": "ydcdei_leader_content_strong_name_v1", "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_ydcdei_leader_content_strong_name_v1",
    "leader_region_selector": ".content p:has(strong)", "name_selector": "strong", "duty_selector": "paragraph_text_after_strong", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "Copyright", "include_selectors": [".searchBox .content"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "普通HTTPS存在TLS握手失败；在线浏览器DOM确认领导简介正文p内strong为姓名，后续文本为职务", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_content_paragraph_strong_name",
    "locator": {"css": {"leader_region_selector": ".searchBox .content p:has(strong)", "name_selector": "strong", "duty_selector": "strong之后的同段落文本"}, "api": {"enabled": False, "reason": "当前渲染DOM直接提供姓名与职务强字段"}, "migration": {"source": "legacy_fixed_people_business_source_and_entry_detail_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".searchBox .content p"):
        name_node = paragraph.select_one("strong")
        if name_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).rstrip("：:").replace(" ", "")
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        prefix = clean_text(name_node.get_text(" ", strip=True))
        duty = clean_text(full_text[len(prefix) :]).lstrip("：: ") if full_text.startswith(prefix) else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=searchBox_content；name=strong；duty=paragraph_suffix；order=dom"})
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
