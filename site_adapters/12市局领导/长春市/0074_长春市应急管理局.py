from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0074", "page_type": "人物列表完整页", "structure_group": "changchun_emergency_title_responsibility_pairs_v2", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_changchun_emergency_title_responsibility_pairs_v2",
    "leader_region_selector": "div.TRS_Editor", "name_selector": "人物标题段末尾姓名", "duty_selector": "人物标题段姓名前原始职务", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.TRS_Editor"], "exclude_selectors": ["iframe"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "主正文按人物标题段与职责段交替排列；登录校验iframe不属于人物内容", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

TITLE_PATTERN = re.compile(r"^(?P<duty>.+(?:局长|主任))(?P<name>[\u4e00-\u9fff·]{2,4})$")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物标题段顺序提取末尾姓名和姓名前原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        match = TITLE_PATTERN.fullmatch(_compact_text(paragraph.get_text(" ", strip=True)))
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": "div.TRS_Editor内人物标题p；末尾姓名；姓名前原始职务"})
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
