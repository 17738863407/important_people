from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2607",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_commerce_leader_menu_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "leader_region_selector": "ul.leader-menus",
    "name_selector": ":scope a[href]",
    "detail_link_selector": ":scope a[href]",
    "risk_flag": "系统DNS不能解析站点子域名，使用Chrome CDP并对详情页执行2路受控并发",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(text: str) -> str:
    """清理页面排版空白，不改变职务语义。"""
    return re.sub(r"\s+", "", text or "")


def normalize_url_identity(url: str) -> tuple[str, str, str, str]:
    """归一化URL身份，忽略HTTP/HTTPS协议差异并保留其余定位信息。"""
    parsed = urlsplit(str(url or "").strip())
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    return hostname, parsed.path or "/", parsed.query, parsed.fragment


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物目录顺序抓取详情页中的姓名和职务字段。"""
    from crawler_core.fetcher import fetch_many_by_chrome_debug

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("ul.leader-menus a[href]")
    source_url_identity = normalize_url_identity(str(page_rule.get("url") or final_url))
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen_urls: set[str] = set()
    candidates: list[tuple[int, str, str]] = []
    for source_order, link in enumerate(links, start=1):
        menu_name = clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not menu_name or not detail_url or detail_url in seen_urls:
            errors.append(f"目录第{source_order}项无有效姓名或详情链接")
            continue
        seen_urls.add(detail_url)
        candidates.append((source_order, menu_name, detail_url))
    if errors or len(candidates) != len(links):
        raise RuntimeError("；".join(errors) or "人物目录链接未完整解析")

    detail_results = fetch_many_by_chrome_debug(
        [detail_url for _order, _name, detail_url in candidates],
        timeout=40,
        max_workers=2,
    )
    for (source_order, menu_name, _detail_url), result in zip(
        candidates,
        detail_results,
        strict=True,
    ):
        detail_soup = BeautifulSoup(result.html, "html.parser")
        info = detail_soup.select_one("dl.leader-info")
        name_node = info.select_one("h4") if info else None
        duty_node = info.select_one("div.leader-text") if info else None
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if name != menu_name or not re.fullmatch(r"[一-鿿·]{2,4}", name) or not duty:
            errors.append(f"目录第{source_order}项与详情字段不一致")
            continue
        detail_url_for_output = result.final_url
        if normalize_url_identity(result.final_url) == source_url_identity:
            detail_url_for_output = ""
        rows.append(
            {
                "order": str(source_order),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url_for_output,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_nanchang_commerce_leader_menu_details_v1",
            }
        )
    if errors or len(rows) != len(links):
        raise RuntimeError("；".join(errors) or "人物目录详情未完整解析")
    return rows


def run_directory_adapter(project_dir: Path) -> Path:
    """使用Chrome读取入口及详情，并统一导出十三列结果。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_by_chrome_debug
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        apply_business_location,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(dict(PAGE_RULE))
    list_result = fetch_by_chrome_debug(str(page_rule["url"]), timeout=40)
    raw_rows = parse_page(list_result.html, list_result.final_url, page_rule)
    rows = normalize_inline_rows(page_rule, raw_rows)
    normalize_record_source_urls(page_rule, rows)
    apply_business_location(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / build_output_name(page_rule["rule_id"], page_rule["organization"])
    export_records(output_path, rows)
    return output_path


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    output_path = run_directory_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
