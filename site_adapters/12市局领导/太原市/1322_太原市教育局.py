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
    "rule_id": "1322",
    "page_type": "人物表格页",
    "structure_group": "taiyuan_education_person_rows_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_education_person_rows_v2",
    "leader_region_selector": "table",
    "name_selector": "人物表每行第二单元格开头姓名",
    "duty_selector": "人物表每行第二单元格姓名后括号内完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面另有信息索引表，人物表单元格还含长篇分工；仅解析符合段首姓名括号职务的行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并单元格排版空白并清理中文标点两侧空格。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表行顺序解析单元格开头的姓名和括号内职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})\s*"
        r"[（(]\s*(?P<evidence>[^（）()]+?)\s*[）)]"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    matched_table_ids: set[int] = set()
    for table_index, table in enumerate(soup.select("table")):
        for row in table.select("tr"):
            cells = row.select(":scope > th, :scope > td")
            if len(cells) != 2:
                continue
            text = clean_text(cells[1].get_text(" ", strip=True))
            match = pattern.match(text)
            if match is None:
                continue
            name = re.sub(r"\s+", "", match.group("name"))
            evidence = clean_text(match.group("evidence"))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
                raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
            if row.select_one("a[href]") is not None:
                raise RuntimeError(f"人物表格行出现未审计链接：{name}")
            matched_table_ids.add(table_index)
            seen_names.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=evidence,
                    detail_url="",
                    evidence=evidence,
                    confidence="high",
                    parser=page_rule["parser"],
                )
            )
    if len(matched_table_ids) != 1 or not records:
        raise RuntimeError(f"人物表数量或人物行异常：tables={len(matched_table_ids)}, rows={len(records)}")
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
