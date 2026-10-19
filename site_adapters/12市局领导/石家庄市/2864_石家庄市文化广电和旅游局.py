from __future__ import annotations

import re
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
    "rule_id": "2864", "page_type": "人物表格页", "structure_group": "sjz_culture_named_columns_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_culture_named_columns_v2",
    "leader_region_selector": "#conN table.Table", "name_selector": "姓名列",
    "duty_selector": "职务列", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同表另有性别与分工情况列，须按表头名称锁定姓名和职务列",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并单元格排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表头名称确定姓名与职务列，并继承数据行顺序。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("#conN table.Table")
    if len(tables) != 1:
        raise RuntimeError(f"领导表格数量异常：{len(tables)}")
    table_rows = tables[0].select("tr")
    if len(table_rows) < 2:
        raise RuntimeError("领导表格缺少数据行")
    headers = [clean_text(cell.get_text(" ", strip=True)) for cell in table_rows[0].find_all(["th", "td"])]
    if headers.count("姓名") != 1 or headers.count("职务") != 1:
        raise RuntimeError(f"领导表格姓名或职务表头异常：{headers}")
    name_index = headers.index("姓名")
    duty_index = headers.index("职务")

    records: list[object] = []
    seen_names: set[str] = set()
    for row in table_rows[1:]:
        cells = row.find_all(["th", "td"])
        if len(cells) != len(headers):
            raise RuntimeError(f"人物数据行列数异常：{len(cells)} != {len(headers)}")
        name = re.sub(r"\s+", "", clean_text(cells[name_index].get_text(" ", strip=True)))
        evidence = clean_text(cells[duty_index].get_text(" ", strip=True))
        evidence = re.sub(r"\s*([，。；：])\s*", r"\1", evidence)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if row.select_one("a[href]") is not None:
            raise RuntimeError(f"人物表格行出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
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
