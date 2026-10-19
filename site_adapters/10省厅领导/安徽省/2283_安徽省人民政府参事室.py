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
    "rule_id": "2283",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "anhui_counsellors_office_profile_heading_v3",
    "leader_region_selector": "div#zoom",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "同页含索引元数据和工作分工，仅解析正文内职务姓名标题",
}


def _clean_text(value: str) -> str:
    """仅清理HTML排版空白，不改写原始语义。"""
    return re.sub(r"\s+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在正文边界内动态解析“职务：姓名”标题，不使用固定人物结果。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for heading in region.select("p"):
        heading_text = _clean_text(heading.get_text(" ", strip=True))
        match = re.fullmatch(r"(.{2,80}?)[：:]\s*([\u3400-\u9fff·\s]{2,12})", heading_text)
        if match is None:
            continue
        duty = _clean_text(match.group(1))
        name = re.sub(r"\s+", "", match.group(2))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)

        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence=page_rule["confidence"],
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
