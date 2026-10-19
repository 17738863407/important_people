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
    "rule_id": "0341",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "beijing_city_management_ldtitle_v3",
    "leader_region_selector": "p.ldTitle",
    "name_selector": "连续NBSP分隔前文本",
    "duty_selector": "连续NBSP分隔后文本",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "姓名可能含内部普通空格，以连续NBSP作为字段边界",
}


def _clean_text(value: object) -> str:
    """仅清理字段首尾和连续排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按p.ldTitle DOM顺序解析姓名和原始职务，详情页为空。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        headline = item.get_text(" ", strip=True).replace("\u3000", " ")
        parts = re.split(r"\u00a0{2,}", headline.strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        duty = _clean_text(
            re.sub(r"[<＜(（]\s*(?:挂职|兼|主持日常工作)\s*[>＞)）]", "", parts[1])
        )
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen_names:
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
