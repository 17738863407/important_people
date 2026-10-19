from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1141",
    "page_type": "人物表格页",
    "structure_group": "jinan_label_value_leader_table_no_colon_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "jinan_label_value_leader_table_no_colon_v1",
    "leader_region_selector": "同时含姓名、职务、领导简历、工作分工标签的table",
    "name_selector": "姓名标签行最后一个单元格",
    "duty_selector": "同一人物块职务标签行最后一个单元格",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "主页面另含非人物iframe，领导信息以主页面静态表格为准",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def cell_text(node) -> str:
    return "".join(node.stripped_strings).replace("\u3000", "").replace("\xa0", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """以姓名标签划分人物块，并读取同块职务标签行。"""
    soup = BeautifulSoup(html, "html.parser")
    target_table = None
    for table in soup.select("table"):
        text = cell_text(table)
        if all(label in text for label in ["姓名", "职务", "领导简历", "工作分工"]):
            target_table = table
            break
    if target_table is None:
        raise ValueError("正文未找到领导信息标签表")
    rows = target_table.select("tr")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        cells = row.find_all(["td", "th"], recursive=False)
        values = [cell_text(cell) for cell in cells]
        if "姓名" not in values:
            continue
        name = values[-1] if values else ""
        duty = ""
        for following in rows[index + 1:]:
            following_cells = following.find_all(["td", "th"], recursive=False)
            following_values = [cell_text(cell) for cell in following_cells]
            if "姓名" in following_values:
                break
            if "职务" in following_values:
                duty = following_values[-1]
                break
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                        "selector_summary": "主页面领导标签表；姓名标签分块；同块职务行强字段"})
    if not records:
        raise ValueError("领导信息表未解析到姓名职务记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
