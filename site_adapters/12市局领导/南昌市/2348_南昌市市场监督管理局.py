from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2348",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_market_supervision_directory_detail_name_duty_row_v3",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "list_to_detail_custom",
    "collector": "playwright",
    "parser": "page_nanchang_market_supervision_directory_detail_name_duty_row_v3",
    "leader_region_selector": "a[href*='/ncsgj/gkldxx/'][href$='.shtml']",
    "name_selector": "目录人物链接文本及详情#zoomcon姓名职务段开头姓名",
    "duty_selector": "详情#zoomcon姓名职务段中姓名后原始职务",
    "detail_link_selector": "a[href*='/ncsgj/gkldxx/'][href$='.shtml']",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_link_selector": "a[href*='/ncsgj/gkldxx/'][href$='.shtml']", "max_detail_links": 30},
    "risk_flag": "系统DNS不能解析站点子域名，使用Chrome CDP并对详情页执行2路受控并发",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "人物目录链接", "detail_row_selector": "#zoomcon.article-content p姓名职务行"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染目录动态发现人物链接，详情#zoomcon姓名职务段直出原始字段"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_directory(html: str, final_url: str) -> list[tuple[str, str]]:
    """按目录DOM顺序动态发现人物姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[href*='/ncsgj/gkldxx/'][href$='.shtml']"):
        name = re.sub(r"\s+", "", normalize_space(link.get_text(" ", strip=True)).lstrip("·"))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or "nav_list.shtml" in detail_url
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    return candidates


def parse_detail(html: str, expected_name: str) -> tuple[str, str]:
    """从详情#zoomcon姓名职务段提取与目录姓名一致的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#zoomcon.article-content")
    if root is None:
        return "", ""
    for paragraph in root.select("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        if not evidence.startswith(expected_name):
            continue
        duty = normalize_space(evidence[len(expected_name) :]).lstrip("：:，, ")
        if re.search(r"(书记|局长|主任|调研员|党组成员|党委委员)", duty):
            return duty, evidence
    return "", ""


def run_directory_adapter(project_dir: Path) -> Path:
    """通过Chrome读取目录，并以2路并发抓取详情后按目录顺序导出。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_by_chrome_debug, fetch_many_by_chrome_debug
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        apply_business_location,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(dict(PAGE_RULE))
    list_result = fetch_by_chrome_debug(str(page_rule["url"]), timeout=40)
    candidates = parse_directory(list_result.html, list_result.final_url)
    if not candidates:
        raise RuntimeError("Chrome渲染后的人物目录解析结果为空")

    raw_rows: list[dict[str, str]] = []
    failed_details: list[str] = []
    detail_results = fetch_many_by_chrome_debug(
        [detail_url for _name, detail_url in candidates],
        timeout=40,
        max_workers=2,
    )
    for (expected_name, detail_url), detail_result in zip(candidates, detail_results, strict=True):
        duty, evidence = parse_detail(detail_result.html, expected_name)
        if not duty:
            failed_details.append(f"{expected_name}:{detail_url}")
            continue
        raw_rows.append(
            {
                "name": expected_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "Chrome渲染目录人物链接按DOM顺序；详情#zoomcon姓名职务强结构段；2路并发后按目录顺序还原；姓名与目录逐项对账",
            }
        )
    if failed_details or len(raw_rows) != len(candidates):
        raise RuntimeError("人物详情未全部验证：" + "；".join(failed_details))

    rows = normalize_inline_rows(page_rule, raw_rows)
    normalize_record_source_urls(page_rule, rows)
    apply_business_location(page_rule, rows)
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
    output_path = run_directory_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
