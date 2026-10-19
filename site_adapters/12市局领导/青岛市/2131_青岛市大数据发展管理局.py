from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2131", "page_type": "人物表格页", "structure_group": "qingdao_gov_department_leader_table_v1", "reuse_scope": "青岛政务网部门机构信息页", "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_direct", "collector": "static_http", "parser": "S012_qingdao_gov_ldxx_table_v1",
    "leader_region_selector": "table#table5", "name_selector": "tr > td[rowspan]:first-child", "duty_selector": "tr中职务标签后的单元格", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "同页多个table#table5；专用解析器只接受同时包含职务和个人简历的领导表", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "css",
    "locator": {"css": {"leader_region_selector": "table#table5", "name_selector": "tr > td[rowspan]:first-child", "duty_selector": "tr中职务标签后的单元格", "detail_link_selector": ""}},
}


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析同时包含“职务”“个人简历”的当前领导表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for table in soup.select("table#table5"):
        if "职务" not in table.get_text(" ", strip=True) or "个人简历" not in table.get_text(" ", strip=True):
            continue
        for row in table.select("tr"):
            cells = row.find_all("td", recursive=False)
            texts = [cell.get_text(" ", strip=True) for cell in cells]
            if "职务" not in texts:
                continue
            duty_index = texts.index("职务")
            if duty_index < 1 or duty_index + 1 >= len(texts):
                continue
            name, duty = texts[duty_index - 1], texts[duty_index + 1]
            if name and duty:
                records.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty})
        if records:
            break
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
