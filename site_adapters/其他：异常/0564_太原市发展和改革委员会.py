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
    "rule_id": "0564",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_fgw_leader_assignment_names_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_fgw_leader_assignment_names_v1",
    "leader_region_selector": "div#zoom.pd20",
    "name_selector": ":scope p",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "当前领导分工页只明确姓名和职责，未提供可核验职务字段；依据说明按规则留空",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(value: str) -> str:
    """移除人物段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导分工段落顺序保留明确姓名，不把主持、协助、分管推断为职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导分工正文命中数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select("p"):
        text = _compact_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"([\u3400-\u9fff·]{2,10})同志(?:主持|协助)", text)
        if not match:
            continue
        name = match.group(1)
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty="",
                detail_url="",
                evidence="",
                confidence="medium",
                parser=page_rule["parser"],
            )
        )

    if not records:
        raise RuntimeError("领导分工正文中未找到明确的姓名同志段")
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
