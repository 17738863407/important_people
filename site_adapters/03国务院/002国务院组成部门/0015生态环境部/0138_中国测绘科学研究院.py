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
    "rule_id": "0138",
    "page_type": "人物表格页",
    "structure_group": "casm_leader_profile_tables_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div#print_html table[align='center']",
    "name_selector": "首行strong末尾中文姓名",
    "duty_selector": "首行strong中姓名前原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物表格同时包含职责、分管及联系单位文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """只清理网页排版空白，不改写职务语义。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _split_heading(text: str) -> tuple[str, str]:
    """拆分“职务 姓名”标题，并清理姓名内部排版空格。"""
    match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,2})", _clean_text(text))
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    return name, _clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表格顺序提取首行明确标注的职务和姓名。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for table in soup.select("div#print_html table[align='center']"):
        heading = next(
            (
                text
                for strong in table.select("tr:first-of-type strong")
                if (text := _clean_text(strong.get_text(" ", strip=True)))
            ),
            "",
        )
        name, duty = _split_heading(heading)
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
                selector_summary="print_html人物表格首行strong职务姓名标题",
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
