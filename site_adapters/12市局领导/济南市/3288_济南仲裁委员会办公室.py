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
    "rule_id": "3288",
    "page_type": "人物表格页",
    "structure_group": "jinan_label_value_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "jinan_label_value_leader_table_v1",
    "leader_region_selector": ".dfnr",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "正文没有#zoom标识；人物区域含长篇工作分工，依据说明仅取同一人物块职务标签行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
}


def cell_text(node) -> str:
    """合并表格单元格文字并清理排版空白。"""
    return "".join(node.stripped_strings).replace("\u3000", "").replace("\xa0", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在正文领导表中以姓名标签分块，只读取同块职务强字段。"""
    del final_url, page_rule
    table = BeautifulSoup(html, "html.parser").select_one(".dfnr table")
    if table is None:
        raise ValueError("正文未找到领导信息表格")
    rows = table.select("tr")
    records: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        values = [cell_text(cell) for cell in row.find_all(["td", "th"], recursive=False)]
        if "姓名：" not in values and "姓名:" not in values:
            continue
        name, duty = values[-1], ""
        for following in rows[index + 1:]:
            next_values = [cell_text(cell) for cell in following.find_all(["td", "th"], recursive=False)]
            if "姓名：" in next_values or "姓名:" in next_values:
                break
            if "职务：" in next_values or "职务:" in next_values:
                duty = next_values[-1]
                break
        if name and duty:
            records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                            "selector_summary": ".dfnr领导表；姓名标签分块；同块职务标签行强字段"})
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
