from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3600", "domain": "www.pszxndrc.org.cn", "page_type": "机构设置领导段落",
    "structure_group": "pszxndrc_leadership_section_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "bounded_colon_name_rows",
    "collector": "static_http", "parser": "page_pszxndrc_leaders_v1",
    "leader_region_selector": "#zoom .TRS_Editor", "name_selector": "#zoom .TRS_Editor > div",
    "duty_selector": "#zoom .TRS_Editor > div", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "bounded_before_department_section", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_names(text: str) -> list[str]:
    """按页面显式空白分隔，并合并相邻单字组成二字姓名。"""
    tokens = re.findall(r"[\u4e00-\u9fff·]+", text)
    names: list[str] = []
    singles: list[str] = []
    for token in tokens:
        if len(token) == 1:
            singles.append(token)
            if len(singles) == 2:
                names.append("".join(singles))
                singles.clear()
        else:
            if singles:
                return []
            if 2 <= len(token) <= 4:
                names.append(token)
    return names if not singles else []


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在“一、中心领导”至“二、处室设置”边界内解析职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoom .TRS_Editor")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    active = False
    for block in region.find_all("div", recursive=False):
        text = block.get_text(" ", strip=True).replace("\u3000", " ")
        compact = re.sub(r"\s+", "", text)
        if compact == "一、中心领导":
            active = True
            continue
        if compact.startswith("二、"):
            break
        if not active:
            continue
        match = re.fullmatch(r"(?P<duty>[^：:]+)[：:](?P<names>.+)", text)
        if match is None:
            continue
        duty = re.sub(r"\s+", "", match.group("duty"))
        for name in parse_names(match.group("names")):
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                         "parser": str(page_rule.get("parser", "")),
                         "selector_summary": "strategy=custom_parse_page；region=#zoom .TRS_Editor；boundary=一、中心领导→二、处室设置；format=职务：姓名"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
