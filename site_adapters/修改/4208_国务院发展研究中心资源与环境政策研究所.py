from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4208", "page_type": "部门领导与工作人员页", "load_mode": "静态 HTML 直出（GB2312）",
    "extract_mode": "list_direct", "parser": "page_inline_drc_department_leaders_v1",
    "leader_region_selector": "body", "name_selector": "", "duty_selector": "", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从领导与工作人员混排区仅保留有明确所长、书记职务的相邻记录。"""
    from bs4 import BeautifulSoup
    if not html:
        from crawler_core.fetcher import fetch_by_raw_requests
        html = fetch_by_raw_requests(str(page_rule["url"])).html
    texts = list(BeautifulSoup(html, "html.parser").stripped_strings)
    start = next(i for i, text in enumerate(texts) if text == "部门领导和工作人员")
    end = next(i for i in range(start + 1, len(texts)) if texts[i].startswith("主办单位"))
    rows: list[dict] = []
    name = ""
    for text in texts[start + 1 : end]:
        compact = "".join(text.split())
        if 2 <= len(compact) <= 4 and all("\u4e00" <= char <= "\u9fff" for char in compact):
            name = compact
        elif name and any(marker in compact for marker in ("所长", "书记")):
            rows.append({"name": name, "duty": compact, "evidence": compact, "detail_url": ""})
            name = ""
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
