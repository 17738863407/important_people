from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "1358",
    "page_type": "人物列表完整页",
    "structure_group": "双列表格左列姓名职务右列分工简历",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".content table",
    "name_selector": "td:first-child p:nth-last-child(2)",
    "duty_selector": "td:first-child p:last-child",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "右列同时包含工作分工和主要简历，必须仅取左列姓名职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([、，,）)])", r"\1", text)
    return re.sub(r"([（(、，,])\s+", r"\1", text).rstrip("。.")


def find_leader_table(soup: BeautifulSoup) -> Tag | None:
    """定位左列姓名职务、右列分工简历的负责人表格。"""
    for table in soup.select(".content table"):
        valid_rows = 0
        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            values = [p.get_text(" ", strip=True) for p in cells[0].select("p") if p.get_text(" ", strip=True)]
            if len(values) >= 2:
                valid_rows += 1
        if valid_rows:
            return table
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格原序提取左列姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    table = find_leader_table(soup)
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in table.select("tr"):
        cells = table_row.select("td")
        if len(cells) < 2:
            continue
        left_values = [
            clean_text(paragraph.get_text(" ", strip=True))
            for paragraph in cells[0].select("p")
            if paragraph.get_text(" ", strip=True)
        ]
        if len(left_values) < 2:
            continue
        name = left_values[-2].replace(" ", "")
        duty = left_values[-1]
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name)
            or not duty
            or name in seen
        ):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".content双列表格左列倒数第二段姓名与末段职务",
            }
        )
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
