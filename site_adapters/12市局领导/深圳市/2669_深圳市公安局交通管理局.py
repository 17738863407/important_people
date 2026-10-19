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
    "rule_id": "2669",
    "page_type": "人物表格页",
    "structure_group": "shenzhen_traffic_leader_tables_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "chrome",
    "extract_mode": "custom_online_path",
    "collector": "chrome_cdp",
    "parser": "page_inline_shenzhen_traffic_leader_tables_v2",
    "leader_heading_selector": ".detatit h4",
    "leader_table_selector": ":scope > table",
    "name_selector": "tr.firstRow",
    "duty_selector": "tr中标签为职务:的第二单元格",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "按机构领导区域中的直接子表提取，排除同页其他导航和机构信息",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """只清理网页表格中的排版空白。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"\s+([，。；：：（）])", r"\1", text)
    return re.sub(r"([，。；：、（])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """按当前页面直接子表顺序读取姓名和职务强字段。"""
    from crawler_core.models import PersonRecord

    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    headings = [
        node
        for node in soup.select(str(page_rule.get("leader_heading_selector") or ""))
        if clean_text(node.get_text(" ", strip=True)) == "机构领导"
    ]
    if not headings:
        return []
    content_cell = headings[-1].find_parent("td")
    if content_cell is None:
        return []

    rows: list[PersonRecord] = []
    seen: set[str] = set()
    for table in content_cell.select(str(page_rule.get("leader_table_selector") or "")):
        first_row = table.select_one("tr.firstRow")
        name = clean_text(first_row.get_text(" ", strip=True) if first_row else "").replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen:
            continue
        evidence = ""
        for table_row in table.select("tr"):
            cells = table_row.find_all(["td", "th"], recursive=False)
            if len(cells) >= 2 and clean_text(cells[0].get_text(" ", strip=True)).rstrip("：:") == "职务":
                evidence = clean_text(cells[1].get_text(" ", strip=True))
                break
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            PersonRecord(
                organization=str(page_rule.get("organization") or ""),
                url=str(page_rule.get("url") or ""),
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=str(page_rule.get("parser") or ""),
                selector_summary=(
                    ".detatit h4=机构领导所在td；直接子table；"
                    "tr.firstRow=姓名；标签职务:所在tr第二单元格=依据"
                ),
                script_sequence=str(page_rule.get("rule_id") or "").zfill(4),
            )
        )
    return rows


def main() -> None:
    """在线采集当前机构领导表格。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
