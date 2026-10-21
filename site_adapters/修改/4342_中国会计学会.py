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
    "rule_id": "4342",
    "page_type": "理事会名单表格页",
    "structure_group": "asc_ninth_council_officers_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_asc_officers_v1",
    "leader_region_selector": "table",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含数百名常务理事和理事；仅抽取会长、常务副会长、副会长、秘书长职务行，空缺不输出。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "officer_rows_before_council_members",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从第九届理事会表格顶部职务行提取学会负责人。"""
    soup = BeautifulSoup(html, "html.parser")
    marker = soup.find(string=lambda value: value and "常务副会长" in value)
    table = marker.find_parent("table") if marker else None
    if table is None:
        raise RuntimeError("未定位到第九届理事会负责人表格")

    rows: list[dict] = []
    current_duty = ""
    seen: set[str] = set()
    for tr in table.find_all("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in tr.find_all(["td", "th"], recursive=False)]
        if not cells:
            continue
        first = re.sub(r"\s+", "", cells[0]).rstrip("：:")
        if first.startswith("常务理事"):
            break
        if first in {"会长", "常务副会长", "副会长", "秘书长"}:
            current_duty = first
            names = cells[1:]
        elif current_duty == "副会长" and not first:
            names = cells[1:]
        else:
            continue
        for value in names:
            name = re.sub(r"\s+", "", value)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) and name not in seen:
                seen.add(name)
                rows.append({"name": name, "duty": current_duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("负责人表格存在，但会长类职务均为空或无法解析")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
