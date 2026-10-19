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
    "rule_id": "4090",
    "page_type": "领导目录与职务表格页",
    "structure_group": "siom_leader_menu_table_pair",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_siom_leader_menu_table_pair",
    "leader_region_selector": "ul.dh_ys_list.zw, table",
    "risk_flag": "姓名和职务分列展示，职务单元格附带研究员头衔，需作确定性后缀清理",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页目录顺序配对姓名和职务表第二列，排除职称后缀。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    names = [re.sub(r"\s+", "", node.get_text(" ", strip=True)) for node in soup.select("ul.dh_ys_list.zw li > a")]
    duties = []
    for row in soup.select("table tr"):
        cells = row.select(":scope > td")
        if len(cells) != 2:
            continue
        text = re.sub(r"\s+", "", cells[1].get_text(" ", strip=True))
        text = re.sub(r"(?:正高级工程师|研究员)$", "", text)
        duties.append(text)
    rows: list[dict[str, str]] = []
    for name, duty_with_name in zip(names, duties):
        duty = duty_with_name.replace(name, "", 1).strip("，、；; ")
        if name and duty and re.search(r"所长|书记|主任|院长", duty):
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
