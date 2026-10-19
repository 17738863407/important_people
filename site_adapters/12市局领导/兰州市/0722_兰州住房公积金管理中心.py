from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0722",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_gjj_hr_separated_leader_sections_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_gjj_hr_separated_leader_sections_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom内各hr片段第一个非空p",
    "duty_selector": "#zoom内各hr片段第二个非空p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "empty_paragraphs_between_fields_and_responsibility_text_after_duty",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "section_separator": "hr",
            "field_selector": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文直接包含由hr分隔的8个人物片段",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def append_section(
    rows: list[dict[str, str]],
    seen_names: set[str],
    section: list[str],
    page_rule: dict,
) -> None:
    """将一个hr分隔片段的前两个非空字段解释为姓名和原始职务。"""
    if len(section) < 2:
        return
    name = re.sub(r"\s+", "", section[0])
    duty = normalize_space(section[1])
    if (
        not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
        or not duty
        or name in seen_names
    ):
        return
    seen_names.add(name)
    rows.append(
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "#zoom内按hr分段；各片段前两个非空p分别为姓名和原始职务，后续主持、负责、主管、分管说明不纳入",
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按hr分隔片段的页面顺序提取领导姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    section: list[str] = []
    for child in container.children:
        node_name = getattr(child, "name", None)
        if node_name == "hr":
            append_section(rows, seen_names, section, page_rule)
            section = []
        elif node_name == "p":
            text = normalize_space(child.get_text(" ", strip=True))
            if text:
                section.append(text)
    append_section(rows, seen_names, section, page_rule)
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
