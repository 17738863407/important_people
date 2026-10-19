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
    "rule_id": "0313", "page_type": "多人物详情合并页", "structure_group": "cpon_leadership_title_colon_fields_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cpon_leadership_title_colon_fields_v1",
    "leader_region_selector": "div.details div.ldbox", "name_selector": "div.tit冒号后", "duty_selector": "div.tit冒号前", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": ["div.details"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "每个人物块正文含简介和分工；姓名、职务均以tit冒号两侧强字段为准，正文不作为主职务依据", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_colon_separated_title_fields",
    "locator": {"css": {"leader_region_selector": "div.details div.ldbox", "title_selector": "div.tit", "body_selector": "div.cnt"}, "api": {"enabled": False, "reason": "原始HTML直接提供人物块标题强字段"}, "migration": {"source": "legacy_business_source_entry_detail_and_offline_claim_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for box in soup.select(page_rule["leader_region_selector"]):
        title_node = box.select_one("div.tit")
        title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        parts = re.split(r"[：:]", title, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = clean_text(parts[0])
        name = clean_text(parts[1]).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leadership_ldbox；fields=title_colon；order=dom"})
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
