from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2771",
    "page_type": "人物表格页",
    "structure_group": "领导分工表格首列姓名职务复合文本",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "table",
    "name_selector": "td:first-child",
    "duty_selector": "td:first-child",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "姓名", "end_anchor": "", "include_selectors": ["table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online会跟随页面脚本跳转而丢失正文表格，须保留原始HTTP响应；第二列职责不得写入职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_space(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导分工表格行顺序拆分首列姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in soup.select("table"):
        header = normalize_space(table.get_text(" ", strip=True))
        if "姓名" not in header.replace(" ", "") or "领导分工" not in header.replace(" ", ""):
            continue
        for table_row in table.select("tr")[1:]:
            cells = table_row.find_all(["td", "th"], recursive=False)
            if len(cells) < 2:
                continue
            first_cell = normalize_space(cells[0].get_text(" ", strip=True))
            match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>.+)", first_cell)
            if match is None or match.group("name") in seen:
                continue
            name = match.group("name")
            duty = normalize_space(match.group("duty")).strip("，,。；;")
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": "领导分工表格首列姓名及职务"})
            seen.add(name)
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
