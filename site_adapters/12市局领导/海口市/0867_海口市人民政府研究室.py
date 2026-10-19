from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0867",
    "page_type": "人物表格页",
    "structure_group": "haikou_leader_label_value_tables",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".TRS_UEDITOR table",
    "name_selector": "各表格精确姓名标签的相邻值单元格",
    "duty_selector": "各表格精确职务标签的相邻值单元格",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "姓名",
        "end_anchor": "分工",
        "include_selectors": [".TRS_UEDITOR table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "每人独立表格并混有电话、基本信息与分工，只按精确姓名职务标签提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select(".TRS_UEDITOR table"):
        fields: dict[str, str] = {}
        for table_row in table.select("tr"):
            cells = table_row.find_all(["th", "td"], recursive=False)
            for index, cell in enumerate(cells[:-1]):
                label = clean_text(cell.get_text(" ", strip=True))
                if label not in {"姓名", "职务"}:
                    continue
                fields[label] = clean_text(cells[index + 1].get_text(" ", strip=True))
        name = fields.get("姓名", "")
        duty = fields.get("职务", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".TRS_UEDITOR人物表格姓名与职务精确标签相邻单元格",
            }
        )
    if not rows:
        raise ValueError("领导正文未发现同时含姓名与职务精确标签的有效人物表格")
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
