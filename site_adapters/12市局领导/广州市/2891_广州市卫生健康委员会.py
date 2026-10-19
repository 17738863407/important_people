from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2891", "page_type": "人物表格页", "structure_group": "人物表格第二列首段姓名党组职务连续文本",
    "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content table", "name_selector": "td:nth-child(2) p:first-child", "duty_selector": "td:nth-child(2) p:first-child",
    "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".article-content table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "第二列首段为姓名党组职务，后续段落含简历和分工必须排除", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物表格行顺序拆分第二列首段中的姓名和党组职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in soup.select(".article-content table tr"):
        cells = table_row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        first_paragraph = cells[1].find("p")
        if first_paragraph is None:
            continue
        heading = compact_text(first_paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,4})(?P<duty>党组.+)", heading)
        if match is None or match.group("name") in seen:
            continue
        name = match.group("name")
        duty = match.group("duty").strip("，,。；;")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": "人物表格第二列首段姓名及党组起始职务"})
        seen.add(name)
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
