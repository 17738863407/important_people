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
    "rule_id": "0462",
    "page_type": "人物分组表格页",
    "structure_group": "图片姓名职务单元格与跨行秘书长名单表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "DalianCppccLeaderTablesParser_v2",
    "leader_region_selector": "ul.middle table.ke-zeroborder",
    "risk_flag": "增强HTTP会跟随脚本跳转至首页；秘书长名单表的职务标题需要按行继承",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一表格排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def _append_record(records: list[dict], seen: set[tuple[str, str]], name: str, duty: str, evidence: str, parser: str) -> None:
    name = _clean_name(name)
    duty = _clean_text(duty).rstrip("：:")
    evidence = _clean_text(evidence).rstrip("：:")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or (name, duty) in seen:
        return
    seen.add((name, duty))
    records.append(
        {
            "name": name,
            "duty": duty,
            "evidence": evidence or duty,
            "detail_url": "",
            "parser": parser,
            "selector_summary": "ul.middle内两张领导表，按单元格及跨行职务标题解析",
        }
    )


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导表网页顺序解析人物，并继承秘书长名单的职务标题。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select(rule["leader_region_selector"])
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    if not tables:
        return records

    for table in tables:
        for cell in table.select("td"):
            parts = cell.find_all("div", recursive=False)
            if len(parts) < 2:
                continue
            name = _clean_text(parts[0].get_text(" ", strip=True))
            duty = _clean_text(parts[1].get_text(" ", strip=True))
            _append_record(records, seen, name, duty, duty, rule["parser"])

    for table in tables:
        if table.select_one("span.lddq") is None:
            continue
        current_duty = ""
        for table_row in table.select("tr"):
            cells = table_row.find_all("td", recursive=False)
            first_text = _clean_text(cells[0].get_text(" ", strip=True)) if cells else ""
            if first_text.endswith(("：", ":")):
                current_duty = first_text.rstrip("：:")
            for name_node in table_row.select("span.lddq"):
                _append_record(records, seen, name_node.get_text(" ", strip=True), current_duty, current_duty, rule["parser"])
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
