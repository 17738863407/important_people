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
    "rule_id": "0586",
    "page_type": "人物表格页",
    "structure_group": "mwr_service_bureau_leader_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "mwr_service_bureau_leader_table_v2",
    "leader_region_selector": "table.boxs",
    "name_selector": "table.boxs table tr td:nth-of-type(2) p:first-of-type",
    "duty_selector": "table.boxs table tr td:nth-of-type(2) p:first-of-type",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务与姓名同处首段；出生年月和学历段落必须排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表格行顺序解析首段中的原始职务和姓名。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for row in region.select("table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2 or cells[0].find("img") is None:
            continue
        first_paragraph = cells[1].find("p", recursive=False)
        label = _clean_text(first_paragraph.get_text(" ", strip=True)) if first_paragraph else ""
        match = re.fullmatch(
            r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,20})",
            label,
        )
        if match is None:
            continue
        duty = _clean_text(match.group("duty"))
        name = re.sub(r"\s+", "", match.group("name"))
        if name in seen:
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
