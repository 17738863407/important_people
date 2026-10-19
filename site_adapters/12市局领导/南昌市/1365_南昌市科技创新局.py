from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1365",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_science_innovation_profile_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_https_upgrade",
    "parser": "page_nanchang_science_innovation_profile_current_sentence_v2",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom人物简介段开头姓名",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "rule_table_http_returns_403_and_work_assignment_paragraphs_follow_profiles",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoom", "row_selector": "#zoom p"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染简介段内直接包含可回指的完整现任句"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简介段DOM顺序提取姓名及同段完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#zoom")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})[，,]", text)
        current_match = re.search(r"(?P<evidence>现任[^。]*。)", text)
        if not name_match or not current_match:
            continue
        name = name_match.group("name")
        evidence = re.sub(r"^现任", "", current_match.group("evidence")).rstrip("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后#zoom简介p按DOM顺序；段首姓名；同一简介段完整现任句；排除后续工作分工段",
            }
        )
    return rows


def run_https_upgraded_adapter(project_dir: Path) -> Path:
    """保留规则主表HTTP依据链接，仅对同域在线采集地址确定性升级HTTPS。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.runner import normalize_inline_rows, normalize_record_source_urls, prepare_records_for_export

    page_rule = apply_business_source(dict(PAGE_RULE))
    source_url = str(page_rule["url"])
    fetch_url = re.sub(r"^http://", "https://", source_url, count=1, flags=re.IGNORECASE)
    fetch_result = fetch_html_with_strategy(fetch_url, strategy="playwright")
    rows = normalize_inline_rows(page_rule, parse_page(fetch_result.html, fetch_result.final_url, page_rule))
    if not rows:
        raise RuntimeError("HTTPS渲染后的科技创新局领导简介解析结果为空")
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / "1365_南昌市科技创新局.txt"
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
    output_path = run_https_upgraded_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
