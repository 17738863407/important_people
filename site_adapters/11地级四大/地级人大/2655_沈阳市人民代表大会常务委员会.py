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
    "rule_id": "2655",
    "page_type": "人物表格页",
    "structure_group": "shenyang_people_congress_profile_tables_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "shenyang_people_congress_profile_tables_v2",
    "leader_region_selector": ".view.TRS_UEDITOR",
    "name_selector": "table strong",
    "duty_selector": "table",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "每个人物由正文直接子表承载，只在对应表内提取姓名和现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文人物表格的原始顺序抽取标题姓名和同表现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for table in region.select(":scope > table"):
        text = _clean_text(table.get_text(" ", strip=True))
        name_match = re.search(r"：\s*(?P<name>[\u3400-\u9fff·]{2,20})", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if not name_match or not evidence_match:
            continue
        name = name_match.group("name")
        evidence = re.sub(r"[\s\u3000\xa0]+", "", evidence_match.group(0))
        evidence = re.sub(r"^现任", "", evidence).rstrip("。")
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
