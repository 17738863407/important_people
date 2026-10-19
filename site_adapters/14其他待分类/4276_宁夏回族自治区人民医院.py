from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4276",
    "page_type": "现任领导卡片列表",
    "structure_group": "宁夏回族自治区人民医院现任领导卡片",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nx_people_hospital_leaders_v1",
    "leader_region_selector": ".ld_lb1",
    "name_selector": ".ld_lb1 .txtk strong",
    "duty_selector": ".ld_lb1 .txtk p:nth-of-type(2)",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "当前领导卡片无独立人物详情页，仅提取卡片中明确展示的姓名和职务。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导卡片顺序提取姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".ld_lb1 > li"):
        name_node = card.select_one(".txtk strong")
        paragraphs = card.select(".txtk p")
        if not name_node or len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", paragraphs[1].get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "现任领导卡片姓名与第二段职务"})
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
