from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0866",
    "page_type": "人物表格页",
    "structure_group": "haikou_tobacco_repeated_label_rows",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".TRS_UEDITOR table",
    "name_selector": "重复姓名标签行的相邻值单元格",
    "duty_selector": "当前人物后续职务标签行的相邻值单元格",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名",
        "end_anchor": "分工",
        "include_selectors": [".TRS_UEDITOR table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "同一表格重复承载五人且混有联系方式、简历、分工，须按姓名行开启人物并只读取紧随职务行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    current_name = ""
    for table_row in soup.select(".TRS_UEDITOR table tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        values = [compact_text(cell.get_text(" ", strip=True)) for cell in cells]
        for index, value in enumerate(values[:-1]):
            if value == "姓名":
                current_name = values[index + 1]
                break
            if value != "职务" or not current_name:
                continue
            duty = values[index + 1]
            if re.fullmatch(r"[\u3400-\u9fff·]{2,12}", current_name) and duty:
                rows.append(
                    {
                        "name": current_name,
                        "duty": duty,
                        "evidence": duty,
                        "detail_url": "",
                        "selector_summary": ".TRS_UEDITOR表格重复姓名行及其后职务标签行",
                    }
                )
            current_name = ""
            break
    if not rows:
        raise ValueError("领导正文未发现姓名标签行及其后职务标签行")
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
