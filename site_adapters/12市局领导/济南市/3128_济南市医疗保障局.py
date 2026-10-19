from __future__ import annotations

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
    "rule_id": "3128",
    "page_type": "人物表格页",
    "structure_group": "jinan_label_value_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "jinan_label_value_leader_table_v1",
    "leader_region_selector": "#zoom table",
    "name_selector": "姓名标签行最后一个单元格",
    "duty_selector": "同一人物块职务标签行最后一个单元格",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "人物区域包含简历和工作分工，依据说明仅取同一人物块的职务标签行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
}


def cell_text(node) -> str:
    """合并单元格内因行内标签拆分的中文文本，并清理排版空白。"""
    return "".join(node.stripped_strings).replace("\u3000", "").replace("\xa0", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名标签划分人物块，只取同块职务标签行的原始强字段。"""
    del final_url, page_rule
    table = BeautifulSoup(html, "html.parser").select_one("#zoom table")
    if table is None:
        raise ValueError("正文未找到领导信息表格")
    rows = table.select("tr")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        values = [cell_text(cell) for cell in row.find_all(["td", "th"], recursive=False)]
        if "姓名：" not in values and "姓名:" not in values:
            continue
        name = values[-1] if values else ""
        duty = ""
        for following in rows[index + 1:]:
            following_values = [cell_text(cell) for cell in following.find_all(["td", "th"], recursive=False)]
            if "姓名：" in following_values or "姓名:" in following_values:
                break
            if "职务：" in following_values or "职务:" in following_values:
                duty = following_values[-1]
                break
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                        "selector_summary": "#zoom表格；姓名标签分块；同块职务标签行强字段"})
    if not records:
        raise ValueError("领导信息表格未解析到姓名职务记录")
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
