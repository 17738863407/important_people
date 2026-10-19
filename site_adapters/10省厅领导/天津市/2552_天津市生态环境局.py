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
    "rule_id": "2552",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_ecology_dash_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_ecology_dash_list_v1",
    "leader_region_selector": "div.content",
    "name_selector": "连续短横线前姓名",
    "duty_selector": "连续短横线后至下一人物前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["div.content"],
        "exclude_selectors": ["面包屑"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "正文使用姓名与连续短横线分隔职务；页面仅有首页和当前栏目链接，不得把入口页写作人物详情",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.content",
            "name_selector": "连续短横线前姓名",
            "duty_selector": "连续短横线后至下一人物前文本",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": ["div.content"], "exclude_selectors": ["面包屑"]},
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文直接列出8组姓名和职务文本"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文连续短横线分隔规则继承人物原顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.content")
    text = _clean_text(region.get_text(" ", strip=True)) if region else ""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"(?P<name>[\u4e00-\u9fff]{2,4})-{5,}(?P<duty>.*?)(?=\s+[\u4e00-\u9fff]{2,4}-{5,}|$)")
    for match in pattern.finditer(text):
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": "custom_tianjin_ecology_dash_list_v1",
            "selector_summary": "div.content；姓名后连续短横线至下一人物前为职务",
        })
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
