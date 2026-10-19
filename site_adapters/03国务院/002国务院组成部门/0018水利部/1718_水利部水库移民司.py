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
    "rule_id": "1718",
    "page_type": "人物列表完整页",
    "structure_group": "mwr_department_leader_table_v2",
    "reuse_scope": "same_site_department_sections",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "mwr_department_leader_table_v2",
    "leader_region_selector": ".sijulist",
    "name_selector": ".sijulist table tr td:nth-of-type(2)",
    "duty_selector": ".sijulist table tr td:first-of-type",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页包含多个机关司局；必须按注入机构匹配唯一分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """定位注入机构对应的机关司局分组，并按表格行和单元格顺序解析。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    expected_title = str(page_rule["organization"]).removeprefix("水利部")
    target_section = None
    for section in soup.select(page_rule["leader_region_selector"]):
        title_node = section.select_one("h4")
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
        if title == expected_title:
            target_section = section
            break
    if target_section is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for row in target_section.select("table tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        duty = _clean_text(cells[0].get_text(" ", strip=True))
        names_text = _clean_text(cells[1].get_text(" ", strip=True))
        if not duty:
            continue
        for raw_name in re.split(r"[、，,]", names_text):
            name = re.sub(r"\s+", "", raw_name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen:
                continue
            seen.add(name)
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
