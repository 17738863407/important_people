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
    "rule_id": "4209", "page_type": "部门领导页", "load_mode": "静态 HTML 直出（GB2312）",
    "extract_mode": "list_direct", "parser": "page_inline_drc_department_leaders_v1",
    "leader_region_selector": ".contentarea .box1:has(> h4)", "name_selector": "", "duty_selector": "", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """提取“部门领导”标题至人员名单前的相邻姓名和所长、副所长职务。"""
    from bs4 import BeautifulSoup
    if not html:
        from crawler_core.fetcher import fetch_by_raw_requests
        html = fetch_by_raw_requests(str(page_rule["url"])).html
    soup = BeautifulSoup(html, "html.parser")
    heading = next((h for h in soup.select(".contentarea .box1 > h4") if h.get_text(" ", strip=True) == "部门领导"), None)
    if heading is None:
        raise RuntimeError("未找到当前部门领导分组")
    region = heading.parent
    rows: list[dict] = []
    for card in region.find_all("div", recursive=False):
        duty_node = card.select_one(":scope > span.leadername")
        name_node = duty_node.find_previous_sibling("span") if duty_node else None
        if name_node is None or duty_node is None:
            continue
        if any(n.has_attr("hidden") or n.get("aria-hidden") == "true" or "display:none" in str(n.get("style", "")).replace(" ", "") for n in [card, *card.parents]):
            continue
        name = "".join(name_node.get_text(" ", strip=True).split())
        evidence = "".join(duty_node.get_text(" ", strip=True).split())
        if name and evidence:
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": ""})
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
