from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2079",
    "page_type": "人物列表完整页",
    "structure_group": "留学服务中心现行领导表格",
    "reuse_scope": "cscse_center_leader_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom_online_flow",
    "collector": "browser_dom",
    "parser": "CscseCurrentLeaderTableParser_v3",
    "leader_region_selector": ".conRight .article_page table",
    "name_selector": "tr有效单元格第1列",
    "duty_selector": "tr有效单元格第2列",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "现行中心领导页直接展示领导表格；站点旧式TLS需浏览器采集，表格首列存在空单元格，人物无独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict,
) -> list[dict]:
    """按现行领导表格行顺序解析姓名与原始职务单元格。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".conRight .article_page table")
    if table is None:
        raise RuntimeError("现行中心领导页未找到目标表格")

    records: list[dict] = []
    seen_names: set[str] = set()
    for row in table.select("tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell]
        if len(cells) < 2:
            continue
        name = re.sub(r"\s+", "", cells[0])
        evidence = cells[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names or not evidence:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".conRight .article_page table tr；过滤空单元格后姓名列+原始职务列",
            }
        )
    if not records:
        raise RuntimeError("现行中心领导表格未解析到人物记录")
    return records


def run_live(output_dir: Path | None = None) -> Path:
    """动态发现现行领导表格并按统一十三列契约导出。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    rule = apply_business_source(PAGE_RULE)
    try:
        current = fetch_html_with_strategy(rule["url"], strategy="online", force_browser=True)
        rows = normalize_inline_rows(rule, parse_page(current.html, current.final_url, rule))
    except Exception as error:
        rows = [make_failure_record(rule, str(error))]

    normalize_record_source_urls(rule, rows)
    prepare_records_for_export(rows)
    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(str(rule["rule_id"]), str(rule["organization"]))
    export_records(output_path, rows)
    return output_path


def main() -> None:
    output_path = run_live()
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
