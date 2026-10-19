from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0121",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_natural_resources_leader_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_https_upgrade",
    "parser": "page_nanchang_natural_resources_leader_duty_paragraphs_v2",
    "leader_region_selector": "div.article-content-body ucapcontent",
    "name_selector": "正文独立姓名职务段落中职务前姓名",
    "duty_selector": "正文独立姓名职务段落中姓名后原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "rule_table_http_returns_403_and_work_assignment_paragraphs_alternate_with_leader_duty_lines",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "div.article-content-body ucapcontent", "row_selector": "p"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染正文按段落直出独立姓名职务行与分工行"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_leader_line(text: str) -> tuple[str, str]:
    """解析独立姓名职务行；工作分工等其他段落返回空值。"""
    evidence = normalize_space(text)
    match = re.fullmatch(
        r"(?P<name>[\u4e00-\u9fff·\s]{2,12}?)\s+"
        r"(?P<duty>(?:党组书记|局长|局党组成员|市土地储备中心主任|二级调研员|三级调研员|四级调研员).{0,80})",
        evidence,
    )
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    duty = normalize_space(match.group("duty"))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文DOM顺序仅提取独立姓名职务行，不拼接工作分工。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.article-content-body ucapcontent") or soup.select_one("div.article-content-body")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.find_all("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        name, duty = parse_leader_line(evidence)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后article-content-body内p按DOM顺序；仅独立姓名职务行，排除工作分工段落",
            }
        )
    return rows


def run_https_upgraded_adapter(project_dir: Path) -> Path:
    """保留规则主表HTTP依据链接，仅对同域在线采集地址确定性升级HTTPS。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.naming import build_output_name
    from crawler_core.runner import normalize_inline_rows, normalize_record_source_urls, prepare_records_for_export

    page_rule = apply_business_source(dict(PAGE_RULE))
    source_url = str(page_rule["url"])
    fetch_url = re.sub(r"^http://", "https://", source_url, count=1, flags=re.IGNORECASE)
    fetch_result = fetch_html_with_strategy(fetch_url, strategy="playwright")
    rows = normalize_inline_rows(page_rule, parse_page(fetch_result.html, fetch_result.final_url, page_rule))
    if not rows:
        raise RuntimeError("HTTPS渲染后的领导介绍正文解析结果为空")
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
    output_path = run_https_upgraded_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
