from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3432",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_government_service_zoom_parenthesized_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_government_service_zoom_parenthesized_leaders_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p > strong括号前姓名",
    "duty_selector": "#zoom p > strong括号内原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "last_person_strong_contains_nested_duty_only_strong_node",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoom", "row_selector": "#zoom p > strong"},
        "api": {"enabled": False, "reason": "当前领导分工页在#zoom静态直出姓名括号职务强结构"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#zoom段落顺序解析直接子strong中的姓名和括号职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in container.find_all("p"):
        strong = paragraph.find("strong", recursive=False)
        if strong is None:
            continue
        evidence = normalize_space(strong.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^（）]{2,80})）[：:]?", evidence)
        if not match:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty")).rstrip("，,；;。")
        if name in seen or not re.search(r"(党组|局长|主任|调研员|巡视员)", duty):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                # 姓名、括号与冒号为标题排版，依据说明只保留括号内可回指职务。
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#zoom正文p按DOM顺序；仅直接子strong姓名括号职务，排除职责正文及嵌套纯职务strong",
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
