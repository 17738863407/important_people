from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3598", "domain": "www.dr-ipmc.org.cn", "page_type": "领导姓名职务卡片",
    "structure_group": "dr_ipmc_leader_boxes_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "leader_box_title_fields",
    "collector": "static_http", "parser": "page_dr_ipmc_leader_boxes_v1",
    "leader_region_selector": ".boxbj-right-body", "name_selector": ".leader-box-title",
    "duty_selector": ".leader-box-title-desc", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "html_comments_excluded_by_dom_parser", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(text: str) -> str:
    """删除姓名和职务中的纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见领导卡片顺序提取标题中的姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".boxbj-right-body")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for box in region.select(".leader-box"):
        title = box.select_one(".leader-box-title")
        duty_node = box.select_one(".leader-box-title-desc")
        if title is None or duty_node is None:
            continue
        name = clean_text(" ".join(str(node) for node in title.find_all(string=True, recursive=False)))
        duty = clean_text(duty_node.get_text(" ", strip=True)).strip("：:/")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                     "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "strategy=custom_parse_page；region=.boxbj-right-body；item=.leader-box；fields=.leader-box-title direct-text+.leader-box-title-desc"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
