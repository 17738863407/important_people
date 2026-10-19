from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2737",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_statistics_profile_heading_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "playwright_stealth_profile": 1,
    "extract_mode": "custom_parse_page",
    "collector": "playwright",
    "parser": "page_nanchang_statistics_profile_heading_v2",
    "leader_region_selector": "领导介绍正文p",
    "name_selector": "简历及分工标题中同志前姓名",
    "duty_selector": "简历及分工标题开头原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "requests_returns_403_and_browser_defense_is_intermittent",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "正文p", "row_selector": "含同志简历及分工的标题p"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染正文标题段直出原始职务、姓名和简历及分工标记"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按标题段DOM顺序解析原始职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>局党组书记、局长|局党组成员、副局长|三级调研员)\s*"
            r"(?P<name>[\u4e00-\u9fff·]{2,8})\s*同志\s*简历及分工",
            evidence,
        )
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后正文p按DOM顺序；含同志简历及分工标题段；标题开头原始职务与同志前姓名；排除简介和分工正文",
            }
        )
    return rows


def run_playwright_adapter(project_dir: Path) -> Path:
    """使用已验证配置1最多六次渲染，取得目标标题后按十三列契约导出。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.runner import normalize_inline_rows, normalize_record_source_urls, prepare_records_for_export

    page_rule = apply_business_source(dict(PAGE_RULE))
    rows = []
    for _attempt in range(6):
        fetch_result = fetch_html_with_strategy(
            str(page_rule["url"]), strategy="playwright", playwright_stealth_profile=1
        )
        rows = normalize_inline_rows(page_rule, parse_page(fetch_result.html, fetch_result.final_url, page_rule))
        if rows:
            break
    if not rows:
        raise RuntimeError("连续6次Playwright配置1渲染后的统计局领导标题解析结果均为空")
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / "2737_人物列表完整页_动态DOM渲染_南昌市统计局.txt"
    export_records(output_path, rows)
    return output_path


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
    output_path = run_playwright_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
