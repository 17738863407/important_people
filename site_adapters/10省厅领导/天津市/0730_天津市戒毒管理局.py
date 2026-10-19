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
    "rule_id": "0730",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_detox_labeled_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_detox_labeled_paragraphs_v1",
    "leader_region_selector": "#zoom .trs_editor_view",
    "name_selector": "姓名标签段",
    "duty_selector": "职务标签段",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名：",
        "end_anchor": "",
        "include_selectors": ["#zoom .trs_editor_view"],
        "exclude_selectors": [],
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
    "risk_flag": "正文按姓名/职务标签重复排列而非表格；职务存在HTML节点拆分空格，网页原文中的“二级巡视员职级”不作语义改写",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom .trs_editor_view",
            "name_selector": "姓名标签段",
            "duty_selector": "职务标签段",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "姓名：",
                "end_anchor": "",
                "include_selectors": ["#zoom .trs_editor_view"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接包含3组明确姓名和职务标签",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _compact_duty(value: str) -> str:
    """合并中文职务被HTML节点拆分后产生的排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标签块原序解析姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#zoom .trs_editor_view")
    text = _clean_text(content.get_text(" ", strip=True) if content else "")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"姓名[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,5})\s*职务[:：]\s*(?P<duty>.*?)(?=\s*姓名[:：]|\s*附件[:：]|$)"
    )

    for match in pattern.finditer(text):
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _compact_duty(match.group("duty"))
        if not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_detox_labeled_paragraphs_v1",
                "selector_summary": "#zoom正文按重复姓名/职务标签块原序解析",
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
