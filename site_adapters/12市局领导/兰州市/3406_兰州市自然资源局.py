from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3406",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_natural_resources_ozoom_name_duty_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_natural_resources_ozoom_name_duty_lines_v1",
    "leader_region_selector": "#ozoom",
    "name_selector": "#ozoom p独立姓名职务短行段首",
    "duty_selector": "#ozoom p独立姓名职务短行中姓名后原字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "first_outer_paragraph_aggregates_all_content_and_responsibility_lines_alternate_with_people",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#ozoom", "row_selector": "#ozoom p"},
        "api": {"enabled": False, "reason": "当前在线#ozoom直出21条独立姓名职务短行，与职责段分离"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#ozoom段落顺序仅接受独立姓名加短职务强结构行。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#ozoom")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in container.find_all("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff·\s]{2,12}?)\s+"
            r"(?P<duty>(?:党组|二级调研员|三级调研员|四级调研员|总规划师|总工程师).{0,55})",
            evidence,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = normalize_space(match.group("duty"))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or name in seen
            or not re.search(r"(党组|局长|调研员|总规划师|总工程师|纪检监察组)", duty)
            or re.search(r"(负责|分管|协助|同志|工作)", duty)
        ):
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#ozoom正文p按DOM顺序；独立姓名加短职务行，排除负责/分管/协助职责段及外层聚合p"})
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
