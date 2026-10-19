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
    "rule_id": "0729",
    "page_type": "人物表格页",
    "structure_group": "tianjin_prison_labeled_tables",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_prison_labeled_tables_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "table内姓名标签",
    "duty_selector": "table内职务标签",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["#zoom table"],
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
    "risk_flag": "每名领导使用独立表格，须遍历全部表格；职务节点存在HTML拆分产生的排版空格",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom table",
            "name_selector": "姓名标签后的单元格文本",
            "duty_selector": "职务标签后的单元格文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": ["#zoom table"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML中6个领导表格直接包含明确姓名和职务标签",
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
    """按表格DOM顺序解析明确的姓名和职务标签。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for table in soup.select("#zoom table"):
        text = _clean_text(table.get_text(" ", strip=True))
        match = re.search(r"姓名[:：]\s*(?P<name>[\u4e00-\u9fff·]{2,5})\s*职务[:：]\s*(?P<duty>.+)$", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _compact_duty(match.group("duty"))
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
        if not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_tianjin_prison_labeled_tables_v1",
                "selector_summary": "#zoom内逐表格按姓名/职务标签解析",
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
