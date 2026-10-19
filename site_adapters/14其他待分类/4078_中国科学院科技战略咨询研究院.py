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
    "rule_id": "4078",
    "page_type": "领导卡片页",
    "structure_group": "casisd_leader_h4_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_casisd_leader_h4_card",
    "leader_region_selector": ".leader",
    "risk_flag": "页面同时保留已卸任人员，须排除任期已结束卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片 DOM 顺序提取当前在任人员及首个职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".leader > ul > li"):
        heading = card.select_one("h4")
        if heading is None:
            continue
        text_nodes = list(heading.find_all(string=True, recursive=False))
        name = re.sub(r"\s+", "", " ".join(str(item) for item in text_nodes)).strip()
        spans = heading.select("span")
        duty = spans[0].get_text(" ", strip=True) if spans else ""
        date_notes = " ".join(span.get_text(" ", strip=True) for span in spans[1:])
        if not name or not duty or re.search(r"20\d{2}\.\d+\s*-\s*20\d{2}\.\d+", date_notes):
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty})
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
