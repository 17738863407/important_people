from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3994",
    "page_type": "学会理事会领导分组页",
    "structure_group": "chinacses_council_leaders",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "online",
    "parser": "custom_chinacses_council_leaders_v1",
    "leader_region_selector": ".NewsText",
    "name_selector": "理事长、秘书长段落及副理事长紧邻表格",
    "duty_selector": "理事长、副理事长、秘书长分组标题",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "理事长",
        "end_anchor": "常务理事",
        "include_selectors": [".NewsText"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口页含顾问、常务理事和全体理事；仅提取理事长、副理事长、秘书长三个明确领导分组。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验渲染DOM中的领导分组标题、紧邻名单表及原始展示顺序。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".NewsText"},
        "api": {"enabled": False, "reason": "渲染DOM已完整提供三个领导分组"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    """清理页面排版空白，不改变文字语义。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip()


def append_row(
    rows: list[dict[str, str]],
    name: str,
    duty: str,
    page_rule: dict[str, object],
) -> None:
    """追加由当前分组标题直接证明的领导记录，并合并同一人的多项职务。"""
    cleaned_name = clean_text(name)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", cleaned_name):
        return
    for row in rows:
        if row["name"] != cleaned_name:
            continue
        duties = row["duty"].split("；")
        if duty not in duties:
            row["duty"] = f'{row["duty"]}；{duty}'
            row["evidence"] = row["duty"]
        return
    rows.append(
        {
            "name": cleaned_name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": ".NewsText 领导分组标题及紧邻名单",
        }
    )


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按理事长、副理事长、秘书长在网页中的原始顺序提取。"""
    del final_url
    root = BeautifulSoup(html, "html.parser").select_one(".NewsText")
    if root is None:
        return []

    rows: list[dict[str, str]] = []
    for child in root.find_all(recursive=False):
        if not isinstance(child, Tag) or child.name != "p":
            continue
        text = clean_text(child.get_text(" ", strip=True))
        if text.startswith("理事长："):
            append_row(rows, text.split("：", 1)[1], "理事长", page_rule)
            continue
        if text.startswith("副理事长："):
            table = child.find_next_sibling("table")
            if table is not None:
                for cell in table.select("td"):
                    append_row(rows, cell.get_text(" ", strip=True), "副理事长", page_rule)
            continue
        if text.startswith("秘书长："):
            append_row(rows, text.split("：", 1)[1], "秘书长", page_rule)
            break
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
