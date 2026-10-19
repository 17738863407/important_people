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
    "rule_id": "1450",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_grain_heading_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_grain_heading_blocks_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "领导标题中中文括号前文本",
    "duty_selector": "领导标题中中文括号内文本",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": [".TRS_Editor"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "领导标题可能由多个内联标签拼接；仅接受短div中的完整“姓名（职务）：”结构",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".TRS_Editor", "name_selector": "领导标题中中文括号前文本", "duty_selector": "领导标题中中文括号内文本", "detail_link_selector": "", "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": [".TRS_Editor"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML正文直接含领导标题与分工"}},
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标题块顺序提取括号前姓名和括号内完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".TRS_Editor")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,5})[（(](?P<duty>[^）)]+)[）)][:：]$")
    for block in scope.select("div") if scope else []:
        text = _compact_text(block.get_text(" ", strip=True))
        if len(text) > 100:
            continue
        match = pattern.fullmatch(text)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_grain_heading_blocks_v1", "selector_summary": ".TRS_Editor短div；完整姓名（原始职务）：标题"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
