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
    "rule_id": "0721",
    "page_type": "人物表格页",
    "structure_group": "jinan_gjj_leader_column_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "jinan_gjj_leader_column_table_v1",
    "leader_region_selector": "含姓名、职务、领导简历、工作分工表头的table",
    "name_selector": "表头姓名列",
    "duty_selector": "表头职务列",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "正文前置面包屑表格须排除；人物链接均为头像图片文件",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态识别领导表头，按数据行原序读取姓名列和职务列。"""
    soup = BeautifulSoup(html, "html.parser")
    target_table = None
    header_values: list[str] = []
    header_row = None
    for table in soup.select("table"):
        for row in table.select("tr"):
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"], recursive=False)]
            if {"姓名", "职务", "领导简历", "工作分工"}.issubset(values):
                target_table, header_values, header_row = table, values, row
                break
        if target_table is not None:
            break
    if target_table is None or header_row is None:
        raise ValueError("正文未找到含完整领导字段表头的信息表")
    name_index = header_values.index("姓名")
    duty_index = header_values.index("职务")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    started = False
    for row in target_table.select("tr"):
        if row is header_row:
            started = True
            continue
        if not started:
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if max(name_index, duty_index) >= len(cells):
            continue
        name = re.sub(r"\s+", "", clean_text(cells[name_index].get_text(" ", strip=True)))
        duty = clean_text(cells[duty_index].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                        "selector_summary": "领导字段表头动态列索引；数据行DOM原序；职务列强字段"})
    if not records:
        raise ValueError("领导信息表未解析到有效姓名职务记录")
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
