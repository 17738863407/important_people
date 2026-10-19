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
    "rule_id": "0952",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_foreign_affairs_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_foreign_affairs_name_duty_paragraphs_v1",
    "leader_region_selector": ".list-con-wrap",
    "name_selector": "p中中文冒号前文本",
    "duty_selector": "p中中文冒号后文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "发布日期",
        "include_selectors": [".list-con-wrap"],
        "exclude_selectors": ["p.time"],
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
    "risk_flag": "姓名和职务同段以中文冒号分隔，后续分工段落不属于主职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".list-con-wrap",
            "name_selector": "p中中文冒号前文本",
            "duty_selector": "p中中文冒号后文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "发布日期",
                "include_selectors": [".list-con-wrap"],
                "exclude_selectors": ["p.time"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文明确提供姓名、职务段落"},
    },
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取冒号两侧的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".list-con-wrap")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select(":scope > p:not(.time)") if scope else []:
        text = _compact_text(paragraph.get_text(" ", strip=True))
        if "：" not in text:
            continue
        name, duty = text.split("：", 1)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_hebei_foreign_affairs_name_duty_paragraphs_v1",
                "selector_summary": ".list-con-wrap直接p；中文冒号前后为姓名、职务",
            }
        )
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
