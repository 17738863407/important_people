from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3670", "page_type": "跨行多组职务姓名表格页",
    "structure_group": "xjtu_current_leader_grid_table_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "xjtu_current_leader_grid_table_v1",
    "leader_region_selector": "#vsb_content table.xxld", "name_selector": "table.xxld a[href]",
    "duty_selector": "table.xxld td", "detail_link_selector": "table.xxld a[href]",
    "content_scope": {"include_selectors": ["#vsb_content table.xxld"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "九列网格含跨行职务区与嵌套表；存在空文本链接和二字姓名字距",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除纯排版空白和字段末尾冒号。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip(" ：:")


def _duty_parts(value: str) -> list[str]:
    """拆分同一字段中明确以顿号并列的职务。"""
    return [part for part in (_clean_text(item) for item in re.split(r"[、；;]", value)) if part]


def _is_duty(value: str) -> bool:
    """识别表格中带字段冒号的职务单元格。"""
    compact = _clean_text(value)
    return bool(compact) and any(word in compact for word in ("书记", "校长", "党委常委", "监察专员"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按虚拟列区间解析跨行网格，并单独解析嵌套职务表。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#vsb_content table.xxld")
    if table is None:
        return []
    people: dict[str, dict[str, object]] = {}

    def add_person(name: str, duties: list[str], href: str) -> None:
        cleaned_name = _clean_text(name)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", cleaned_name):
            return
        detail_url = urljoin(final_url, href) if href else ""
        person = people.setdefault(cleaned_name, {"duties": [], "detail_url": detail_url})
        for duty in duties:
            if duty and duty not in person["duties"]:
                person["duties"].append(duty)
        if not person["detail_url"] and detail_url:
            person["detail_url"] = detail_url

    column_duties: dict[int, list[str]] = {}
    tbody = table.find("tbody", recursive=False)
    for row in tbody.find_all("tr", recursive=False) if tbody is not None else []:
        cells = row.find_all(["td", "th"], recursive=False)
        if any(cell.find("table", recursive=False) is not None for cell in cells):
            continue
        positioned: list[tuple[int, int, object]] = []
        column = 0
        for cell in cells:
            width = int(cell.get("colspan", 1) or 1)
            positioned.append((column, column + width, cell))
            column += width
        labels = [(start, end, _duty_parts(cell.get_text(" ", strip=True))) for start, end, cell in positioned if _is_duty(cell.get_text(" ", strip=True)) and not cell.select("a")]
        for index, (start, end, duties) in enumerate(labels):
            next_start = labels[index + 1][0] if index + 1 < len(labels) else max(column, 9)
            for target_column in range(end, next_start):
                column_duties[target_column] = duties
        for start, _, cell in positioned:
            duties = column_duties.get(start, [])
            for anchor in cell.find_all("a", recursive=True):
                add_person(anchor.get_text(" ", strip=True), duties, str(anchor.get("href", "")).strip())

    for nested in table.select(":scope table"):
        first_row = nested.select_one("tr")
        if first_row is None:
            continue
        first_cell = first_row.find(["td", "th"], recursive=False)
        duties = _duty_parts(first_cell.get_text(" ", strip=True)) if first_cell is not None else []
        if not duties:
            continue
        for anchor in nested.select("a[href]"):
            add_person(anchor.get_text(" ", strip=True), duties, str(anchor.get("href", "")).strip())

    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary="#vsb_content table.xxld按colspan展开的职务列区与嵌套职务表",
        ) for name, person in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
