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
    "rule_id": "1101",
    "page_type": "人物表格页",
    "structure_group": "iwhr_leader_heading_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "防护页后浏览器渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_iwhr_leader_heading_blocks_v2",
    "leader_region_selector": "td.skgkcontent",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["td.skgkcontent"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "直接HTTP返回412；在线编排经浏览器取得正文，只解析内容块内无上级粗体祖先的职务姓名标题，排除履历项目",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_heading_blocks",
    "locator": {
        "css": {"leader_region_selector": "td.skgkcontent", "heading_selector": "b, strong"},
        "api": {"enabled": False, "reason": "当前渲染DOM的领导内容块标题直接提供职务和姓名"},
        "migration": {
            "source": "legacy_fixed_duty_vocabulary_and_business_source_removed",
            "verified_status": "verified_current_online_browser",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从领导内容块的粗体标题中动态拆分“职务 姓名”。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one("td.skgkcontent")
    if block is None:
        return []

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for heading in block.select("b, strong"):
        if heading.find_parent(["b", "strong"]) is not None:
            continue
        text = _clean_text(heading.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,20})", text)
        if match is None:
            continue
        duty, name = match.group(1), match.group(2)
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="td.skgkcontent内顶层b/strong职务姓名标题",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
