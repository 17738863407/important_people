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
    "rule_id": "2066",
    "page_type": "人物表格页",
    "structure_group": "pbc_spokesperson_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "含新闻发言人表头的最小table",
    "name_selector": "tbody tr数据行 td:first-of-type",
    "duty_selector": "tbody tr数据行 td:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页包含新闻列表、机构职责、内设机构及联系方式",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理表格排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """依据新闻发言人表头定位最小表格，并按数据行提取前两列。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        if candidate.find("table") is not None:
            continue
        candidate_rows = candidate.find_all("tr")
        if not candidate_rows:
            continue
        header_cells = candidate_rows[0].find_all(["td", "th"], recursive=False)
        header_texts = [_clean_text(cell.get_text(" ", strip=True)) for cell in header_cells]
        if header_texts[:2] == ["新闻发言人", "职务"]:
            table = candidate
            break
    if table is None:
        raise RuntimeError("未找到新闻发言人表格")

    records: list[PersonRecord] = []
    for row in table.select("tr")[1:]:
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        name = _clean_text(cells[0].get_text(" ", strip=True)).replace(" ", "")
        duty = _clean_text(cells[1].get_text(" ", strip=True))
        if not name or not duty:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="新闻发言人最小表格数据行前两列",
            )
        )
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
