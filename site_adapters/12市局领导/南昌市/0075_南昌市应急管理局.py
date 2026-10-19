from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0075",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_emergency_leader_title_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_https_upgrade",
    "parser": "page_nanchang_emergency_leader_title_list_v2",
    "leader_region_selector": "ul.pageList.newsList",
    "name_selector": "ul.pageList.newsList > li a[title]标题末尾姓名",
    "duty_selector": "ul.pageList.newsList > li a[title]标题姓名前原始职务",
    "detail_link_selector": "ul.pageList.newsList > li a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "list_dynamic_links",
        "detail_link_selector": "ul.pageList.newsList > li a[href][title]",
        "max_detail_links": 20,
    },
    "risk_flag": "rule_table_http_returns_403_while_same_host_https_playwright_is_current_valid_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "ul.pageList.newsList", "row_selector": "ul.pageList.newsList > li"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染列表直接提供姓名职务标题及一一对应人物详情链接"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def split_duty_name(text: str) -> tuple[str, str]:
    """从列表原始标题末尾拆分姓名，通知等非人物标题返回空值。"""
    cleaned = normalize_space(text)
    if re.search(r"(通知|分工|调整)", cleaned):
        return "", ""
    match = re.fullmatch(
        r"(?P<duty>.+?(?:书记|局长|主任|调研员|巡视员))\s*(?P<name>[\u4e00-\u9fff·]{2,8})",
        cleaned,
    )
    if not match:
        return "", ""
    return normalize_space(match.group("duty")), match.group("name")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导信息列表DOM顺序提取人物标题及动态详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.pageList.newsList > li"):
        link = item.select_one("a[href][title]")
        if link is None:
            continue
        evidence = normalize_space(link.get("title") or link.get_text(" ", strip=True))
        duty, name = split_duty_name(evidence)
        if not name or not duty or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not detail_url or detail_url == final_url:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后ul.pageList.newsList直属li按DOM顺序；a[title]末尾姓名及前置职务；排除通知/分工/调整标题",
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
        raise RuntimeError("HTTPS渲染后的领导信息列表解析结果为空")
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
