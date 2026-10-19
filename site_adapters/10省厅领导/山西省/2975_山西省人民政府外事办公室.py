from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩段落排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导信息段落顺序拆分末尾姓名及前部完整职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".jigou_con p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,8})$", text)
        if match is None or match.group("name") in seen:
            continue
        name, evidence = match.group("name"), clean_text(match.group("duty"))
        if not re.search(r"主任|巡视员|副会长|党组|书记", evidence):
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_foreign_affairs_paragraphs_v2",
                     "selector_summary": "leader=.jigou_con p；name=last token；duty=text before name；detail=none"})
    return rows


PAGE_RULE = {
    "rule_id": "2975", "page_type": "人物列表完整页", "structure_group": "shanxi_foreign_affairs_paragraphs", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_foreign_affairs_paragraphs_v2",
    "leader_region_selector": ".jigou_con p", "name_selector": "paragraph last token", "duty_selector": "paragraph text before name", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".jigou_con"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "raw_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "领导信息为职务在前、姓名在后的纯文本段落，使用最小正文容器和职务关键词校验", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".jigou_con p", "name_selector": "paragraph last token", "duty_selector": "paragraph text before name", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".jigou_con"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导段落已直出姓名和职务"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
