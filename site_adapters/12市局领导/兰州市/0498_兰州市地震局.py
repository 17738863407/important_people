from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0498",
    "page_type": "人物表格页",
    "structure_group": "lanzhou_earthquake_name_duty_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_earthquake_name_duty_paragraphs_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p开头中文括号前姓名",
    "duty_selector": "#zoom p开头中文括号内原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "metadata_contains_stale_names_and_responsibilities_follow_duty",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "paragraph_selector": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文直接包含姓名、括号内原始职务及其后分工说明",
        },
    },
}


LEADER_PATTERN = re.compile(
    r"^(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^（）]{2,80})）[:：]"
)


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取开头姓名和括号内原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in container.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        match = LEADER_PATTERN.match(text)
        if match is None:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#zoom内逐段；仅取段首姓名及中文括号内原始职务，不纳入冒号后的主持、负责和分管说明",
            }
        )
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
