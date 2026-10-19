from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1758",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_civil_affairs_leader_title_name_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_civil_affairs_leader_title_name_duty_v1",
    "leader_region_selector": ".zfxxgk_subtit + .zfxxgk_subcon",
    "name_selector": "领导之窗li a[title]职务关键词前姓名",
    "duty_selector": "领导之窗li a[title]职务关键词起始的原始职务",
    "detail_link_selector": "领导之窗li a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".zfxxgk_subcon li a[title][href]",
        "max_detail_links": 20,
    },
    "risk_flag": "name_and_duty_are_combined_in_title_with_variable_spacing",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_heading_selector": ".zfxxgk_subtit",
            "leader_container_selector": ".zfxxgk_subtit + .zfxxgk_subcon",
            "leader_link_selector": "li a[title][href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态领导之窗列表title字段直接包含10人的姓名和原始职务，并提供独立人物链接",
        },
    },
}


DUTY_START_PATTERN = re.compile(
    r"局党组|党组|市民政局|一级|二级|三级|四级|驻局|局长|副局长|调研员"
)


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def split_name_duty(text: str) -> tuple[str, str]:
    """按首个明确职务起点拆分合并title字段。"""
    normalized = normalize_space(text)
    match = DUTY_START_PATTERN.search(normalized)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", normalized[: match.start()])
    duty = normalize_space(normalized[match.start() :])
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅在领导之窗相邻容器内按列表顺序解析合并title字段。"""
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (
            node
            for node in soup.select(".zfxxgk_subtit")
            if normalize_space(node.get_text(" ", strip=True)) == "领导之窗"
        ),
        None,
    )
    container = heading.find_next_sibling("div", class_="zfxxgk_subcon") if heading else None
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in container.select("li a[title][href]"):
        evidence = normalize_space(str(link.get("title", "")))
        name, duty = split_name_duty(evidence)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href", "")).strip()),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导之窗相邻容器li a[title]；首个明确职务关键词前后拆分姓名和原始职务；href为动态人物页",
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
