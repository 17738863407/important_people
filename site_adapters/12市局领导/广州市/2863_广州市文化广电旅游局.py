from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2863", "page_type": "人物表格页", "structure_group": "逐人物嵌套双行表格",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "list_direct", "collector": "raw_http", "parser": "builtin_parse_page",
    "leader_region_selector": "table", "name_selector": "tr:first-child td", "duty_selector": "tr:first-child td",
    "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online会跟随页面脚本跳转至空搜索页，须保留原始HTTP响应；人物嵌套表格只解析两行叶子表并排除第二行分工", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按叶子表格DOM顺序拆分首行中的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in soup.select("table"):
        if table.find("table") is not None:
            continue
        table_rows = table.select("tr")
        if len(table_rows) != 2:
            continue
        first_row = clean_text(table_rows[0].get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>.+)", first_row)
        if match is None or match.group("name") in seen:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty")).strip("，,。；;")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": "无子表格的逐人物双行表格首行姓名职务"})
        seen.add(name)
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
