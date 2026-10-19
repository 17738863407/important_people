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
    "rule_id": "1996",
    "page_type": "人物表格页",
    "structure_group": "jinan_label_value_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "V002_table_label_value_v1",
    "leader_region_selector": "div#zoom > div > table",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "人物区域包含长篇工作分工，V002仅接受姓名及职务标签行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
}


def clean_text(value: str) -> str:
    """归一化表格标签值的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只按同一人物相邻的姓名、职务标签行提取，不读取简历和工作分工。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("div#zoom > div > table")
    if table is None:
        raise RuntimeError("未定位到济南市自然资源和规划局领导表格")

    rows: list[dict[str, str]] = []
    current_name = ""
    for table_row in table.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in table_row.find_all(["th", "td"], recursive=False)]
        if not cells:
            continue
        if any(text.startswith("姓名") for text in cells):
            current_name = re.sub(r"\s+", "", cells[-1])
            continue
        if current_name and cells[0].startswith("职务"):
            evidence = re.sub(r"^现任\s*", "", cells[-1])
            rows.append(
                {
                    "name": current_name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": "",
                    "parser": "page_jinan_label_value_leader_table_v1",
                    "selector_summary": "div#zoom > div > table；姓名行后紧邻职务行；排除简历与工作分工",
                }
            )
            current_name = ""
    if not rows:
        raise RuntimeError("领导表格未解析到姓名和职务标签行")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
