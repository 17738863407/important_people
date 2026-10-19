from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0477",
    "page_type": "人物表格页",
    "structure_group": "haikou_label_value_name_duty_rows",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "精确姓名与职务标签表格行",
    "name_selector": "姓名标签后的值单元格",
    "duty_selector": "当前姓名后的职务标签值单元格",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导班子及分工",
        "end_anchor": "相关附件",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "页面含多层嵌套表格，按精确标签顺序绑定姓名与职务值",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    current_name = ""
    for table_row in soup.select("tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if "姓名" in values:
            label_index = values.index("姓名")
            current_name = compact_text(values[label_index + 1]) if label_index + 1 < len(values) else ""
            if current_name and not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", current_name):
                current_name = ""
            continue
        if not current_name or not values or values[0] != "职务" or len(values) < 2:
            continue
        duty = compact_text(values[1]).rstrip("。")
        duty = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", duty).strip()
        if not duty:
            raise ValueError(f"姓名后的职务标签值为空：{current_name}")
        rows.append(
            {
                "name": current_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "嵌套表格精确姓名标签及后续职务标签值",
            }
        )
        current_name = ""
    if not rows:
        raise ValueError("领导信息表未发现可验证的姓名职务标签行")
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
