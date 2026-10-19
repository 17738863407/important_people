from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0372",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_finance_colon_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright",
    "parser": "page_nanchang_finance_colon_duty_paragraphs_v2",
    "leader_region_selector": ".contentShow",
    "name_selector": ".contentShow p中冒号前姓名",
    "duty_selector": ".contentShow p中冒号后首句完整原始职务",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "AB岗制", "include_selectors": [".contentShow"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "requests_returns_403_and_work_assignment_paragraphs_alternate_with_leader_duty_lines",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".contentShow", "row_selector": ".contentShow p", "end_anchor": "AB岗制"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染正文按段落直出姓名冒号职务行，AB岗制为明确终止边界"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取AB岗制之前的独立姓名冒号职务行。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".contentShow")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        if evidence.startswith("AB岗制"):
            break
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·\s]{2,12}?)[:：](?P<duty>[^。]{2,100})。?", evidence)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = normalize_space(match.group("duty")).strip("，、；;")
        duty = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", duty)
        duty = duty.strip()
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or name in seen
            or "市财政局" not in duty
            or not re.search(r"(党组|局长|主任|调研员|纪检监察组)", duty)
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后.contentShow p按DOM顺序；冒号前姓名、冒号后完整首句原始职务；AB岗制终止；排除交替分工段",
            }
        )
    return rows


def run_playwright_adapter(project_dir: Path) -> Path:
    """使用规则主表入口在线渲染，并按现行十三列契约导出。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.runner import normalize_inline_rows, normalize_record_source_urls, prepare_records_for_export

    page_rule = apply_business_source(dict(PAGE_RULE))
    fetch_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="playwright")
    rows = normalize_inline_rows(page_rule, parse_page(fetch_result.html, fetch_result.final_url, page_rule))
    if not rows:
        raise RuntimeError("Playwright渲染后的财政局领导正文解析结果为空")
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / "0372_人物列表完整页_动态DOM渲染_南昌市财政局.txt"
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
