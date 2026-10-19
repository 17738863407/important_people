from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3202", "page_type": "人物表格页", "structure_group": "姓名与简介工作分工双列表格",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content table", "name_selector": "td:first-child", "duty_selector": "td:nth-child(2)",
    "detail_link_selector": "", "content_scope": {"start_anchor": "姓名", "end_anchor": "", "include_selectors": [".article-content table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "右列同时含简介和工作分工，仅提取当前人物单元格内完整现任句", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按双列表格行顺序提取姓名及右侧简介中的完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table_row in soup.select(".article-content table tr"):
        cells = table_row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        name = compact_text(cells[0].get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or name in seen:
            continue
        profile = compact_text(cells[1].get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", profile)
        if current_match is None:
            continue
        evidence = current_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": "姓名简介工作分工双列表格右列完整现任句"})
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
