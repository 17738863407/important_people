from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2812", "page_type": "人物表格页", "structure_group": "姓名职务分工简历四列表格",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": "table", "name_selector": "td:first-child", "duty_selector": "td:nth-child(2)",
    "detail_link_selector": "", "content_scope": {"start_anchor": "姓名", "end_anchor": "", "include_selectors": ["table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面另有元数据表，必须以姓名职务分工简历四列表头锁定人物表格", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按四列表格行顺序提取前两列的姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select("table"):
        table_rows = table.select("tr")
        if not table_rows:
            continue
        header = [clean_text(cell.get_text(" ", strip=True)) for cell in table_rows[0].find_all(["td", "th"], recursive=False)]
        if header[:4] != ["姓名", "职务", "分工", "简历"]:
            continue
        for table_row in table_rows[1:]:
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in table_row.find_all(["td", "th"], recursive=False)]
            if len(cells) < 2 or re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", cells[0]) is None or not cells[1]:
                continue
            rows.append({"name": cells[0], "duty": cells[1], "evidence": cells[1], "detail_url": "", "selector_summary": "姓名职务分工简历四列表格前两列"})
        break
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
