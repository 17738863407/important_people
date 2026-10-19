from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2437",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_audit_profile_trailing_duty_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright",
    "parser": "page_nanchang_audit_profile_trailing_duty_v2",
    "leader_region_selector": "#zoomcon",
    "name_selector": "#zoomcon人物简介段开头姓名",
    "duty_selector": "人物简介段末尾原始职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "requests_returns_403_and_work_assignment_paragraph_follows_each_profile",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoomcon", "row_selector": "#zoomcon p"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染多人简介段末尾直接包含原始职务字段"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简介段DOM顺序提取段首姓名和末尾职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#zoomcon")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff·]{2,8})[，,][男女][，,].*?[，,]"
            r"(?P<duty>[^，。]*(?:党组|局长|主管|总审计师|副局长)[^。]*)。",
            evidence,
        )
        if not match:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后#zoomcon p按DOM顺序；人物简介段首姓名、末尾原始职务字段；排除后续分工段",
            }
        )
    return rows


def run_playwright_adapter(project_dir: Path) -> Path:
    """最多三次在线渲染，取得非空多人简介后按十三列契约导出。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.naming import build_output_name
    from crawler_core.runner import normalize_inline_rows, normalize_record_source_urls, prepare_records_for_export

    page_rule = apply_business_source(dict(PAGE_RULE))
    rows = []
    for _attempt in range(3):
        fetch_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="playwright")
        rows = normalize_inline_rows(page_rule, parse_page(fetch_result.html, fetch_result.final_url, page_rule))
        if rows:
            break
    if not rows:
        raise RuntimeError("连续3次Playwright渲染后的审计局人物简介解析结果均为空")
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / build_output_name(page_rule["rule_id"], page_rule["organization"])
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
