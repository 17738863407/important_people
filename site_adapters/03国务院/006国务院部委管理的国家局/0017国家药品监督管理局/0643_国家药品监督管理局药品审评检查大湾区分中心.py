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
    "rule_id": "0643", "page_type": "人物列表完整页", "structure_group": "gbacdei_name_colon_duty_paragraphs_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_gbacdei_name_colon_duty_paragraphs_v2",
    "leader_region_selector": ".content", "name_selector": "p strong冒号前姓名", "duty_selector": "同段冒号后文本", "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "", "include_selectors": [".content"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 5},
    "risk_flag": "正文标题也含strong，仅接受完整匹配‘姓名：职务’的直属人物段落", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".content", "person_selector": ":scope > p:has(strong)"}, "api": {"enabled": False, "reason": "原始HTML人物段落直接提供姓名与职务"}, "migration": {"source": "current_name_colon_duty_paragraphs", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    regions = [
        region
        for region in soup.select(page_rule["leader_region_selector"])
        if "领导简介" in clean_text(region.get_text(" ", strip=True))
        and region.select_one(":scope .content") is None
    ]
    if len(regions) != 1:
        raise RuntimeError(f"领导简介正文数量异常：{len(regions)}")
    rows: list[dict[str, str]] = []
    for paragraph in regions[0].select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,10})[：:](?P<duty>.+)", text)
        if match is None:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty"))
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "唯一领导简介.content直属p；姓名冒号职务；order=paragraph"})
    if not rows:
        raise RuntimeError("领导简介正文未提取到人物段落")
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
