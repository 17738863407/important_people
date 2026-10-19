from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {"rule_id": "3606", "domain": "www2023.cau.edu.cn", "page_type": "领导姓名职务表格卡片",
    "structure_group": "cau_present_tables_2026", "reuse_scope": "single_page", "load_mode": "静态HTML直出",
    "fetch_mode": "online", "extract_mode": "present_table_labels_name", "collector": "static_http",
    "parser": "page_cau_current_leaders_v1", "leader_region_selector": ".present-table", "name_selector": ".name",
    "duty_selector": ".label", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "exclude_biography_and_empty_placeholder", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page"}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导表格卡片的网页顺序抽取姓名与全部职务标签。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select("table.present-table"):
        name_node = table.select_one(".name")
        name = clean(name_node.get_text(" ", strip=True) if name_node else "")
        duties = [clean(node.get_text(" ", strip=True)) for node in table.select(".label")]
        duties = [duty for duty in duties if duty]
        if duties and re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
            duty = "；".join(dict.fromkeys(duties))
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                         "parser": str(page_rule.get("parser", "")),
                         "selector_summary": "strategy=custom_parse_page；item=table.present-table；fields=.label+.name；empty=excluded"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
