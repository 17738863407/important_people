from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "1754",
    "page_type": "人物表格页",
    "structure_group": "姓名职务职级分工三列表格",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content table",
    "name_selector": "td:nth-child(1)",
    "duty_selector": "td:nth-child(2)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务与分工分列，必须排除第三列职责文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def find_leader_table(soup: BeautifulSoup) -> Tag | None:
    """按稳定表头定位领导班子表格，不依赖人物姓名。"""
    for table in soup.select(".article-content table"):
        first_row = table.select_one("tr")
        if first_row is None:
            continue
        headers = [
            clean_text(cell.get_text(" ", strip=True)).replace(" ", "")
            for cell in first_row.find_all(["th", "td"])
        ]
        if len(headers) >= 3 and headers[0] == "姓名" and "职务" in headers[1] and headers[2] == "分工":
            return table
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按表格原序提取姓名列和职务列。"""
    soup = BeautifulSoup(html, "html.parser")
    table = find_leader_table(soup)
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in table.select("tr")[1:]:
        cells = table_row.find_all(["th", "td"])
        if len(cells) < 3:
            continue
        name = clean_text(cells[0].get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(cells[1].get_text(" ", strip=True))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name)
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
                "selector_summary": ".article-content领导表格姓名列与职务职级列",
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
