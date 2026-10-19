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
    "rule_id": "1294",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_prison_leaf_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_prison_leaf_paragraphs_v1",
    "leader_region_selector": "#fontzoom",
    "name_selector": "无子p的p文本首字段",
    "duty_selector": "无子p的p文本姓名后字段",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导介绍", "end_anchor": "关键词", "include_selectors": ["#fontzoom"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "源HTML存在非法嵌套p；只解析不含子p的叶子段落，避免首人聚合全部人物",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#fontzoom", "name_selector": "无子p的p文本首字段", "duty_selector": "无子p的p文本姓名后字段", "detail_link_selector": "", "content_scope": {"start_anchor": "领导介绍", "end_anchor": "关键词", "include_selectors": ["#fontzoom"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导正文直接含姓名和职务叶子段落"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按叶子段落DOM顺序提取姓名及其后的完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#fontzoom")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select("p") if scope else []:
        if paragraph.find("p") is not None:
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)$", text)
        if not match:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_prison_leaf_paragraphs_v1", "selector_summary": "#fontzoom无子p的叶子段落；首字段姓名、后续完整职务"})
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
