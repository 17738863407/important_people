from __future__ import annotations

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Comment


PAGE_RULE = {
    "rule_id": "2590",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_party_committee_grouped_names_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_nanning_party_committee_grouped_names_v3",
    "leader_region_selector": ".content .dwld",
    "name_selector": ".dwld直属div内人物锚文本",
    "duty_selector": "各直属div前HTML分组注释（书记、副书记、常委）",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物锚点为javascript:void(0)，没有独立详情页；职务仅按官网分组注释提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".content .dwld", "name_selector": "直属div内a锚文本", "duty_selector": "直属div前HTML分组注释"}, "api": {"enabled": False, "reason": "市委领导姓名与分组职务均由静态HTML直出"}},
}


def compact_layout(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def discover_people(html: str) -> list[tuple[str, str]]:
    """按官网分组注释与直属人物容器顺序提取姓名、职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content .dwld")
    if region is None:
        return []
    people: list[tuple[str, str]] = []
    seen: set[str] = set()
    current_duty = ""
    valid_duties = {"书记", "副书记", "常委"}
    for child in region.children:
        if isinstance(child, Comment):
            label = compact_layout(str(child))
            if label in valid_duties:
                current_duty = label
            continue
        if getattr(child, "name", None) != "div" or not current_duty:
            continue
        for anchor in child.select("a"):
            name = compact_layout(anchor.get_text(" ", strip=True))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
                continue
            seen.add(name)
            people.append((name, current_duty))
    return people


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    people = discover_people(html)
    if not people:
        return []
    rows: list[dict[str, str]] = []
    for name, evidence in people:
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "scope=.content .dwld；按直属div前书记、副书记、常委注释分组；人物锚文本按DOM顺序"})
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
