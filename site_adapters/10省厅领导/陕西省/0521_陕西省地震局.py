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
    "rule_id": "0521",
    "page_type": "人物列表完整页",
    "structure_group": "leader_profile_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiEarthquakeLeaderTableParser_v1",
    "leader_region_selector": "#vsb_content table tr",
    "name_selector": "td p strong首个空白前文本",
    "duty_selector": "td p strong首个空白后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "每行还含履历和职责，只允许读取首个strong职务行",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按表格行顺序提取首个加粗段落中的姓名和职务。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in soup.select("#vsb_content table tr"):
        title_node = row.select_one("td p strong")
        if title_node is None:
            continue
        title = _clean_text(title_node.get_text(" ", strip=True))
        parts = title.split(" ", 1)
        if len(parts) != 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        duty = _clean_text(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "#vsb_content table tr；姓名/职务=td p strong首个空白分隔",
                "order": str(len(records) + 1),
            }
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
