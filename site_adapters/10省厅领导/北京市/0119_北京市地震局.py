from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0119",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "beijing_earthquake_leader_title_v3",
    "collector": "curl_schannel_tls_fallback",
    "leader_region_selector": "li.list div.fl",
    "name_selector": "a[title]标题末尾姓名",
    "duty_selector": "a[title]标题姓名前原始文本",
    "detail_link_selector": "a[title][href]",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "medium",
    "risk_flag": "站点与Python OpenSSL握手不兼容，使用Windows curl Schannel在线采集",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导链接标题动态解析“原始职务 姓名”，不使用固定人物结果。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for link in soup.select(f"{page_rule['leader_region_selector']} a[title][href]"):
        title = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.{2,100}?)\s+([\u3400-\u9fff·]{2,8})", title)
        if match is None:
            continue
        duty, name = (_clean_text(part) for part in match.groups())
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip("，,；; ")
        if name in seen_names or not duty:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, _clean_text(link.get("href")))
        if detail_url == final_url:
            detail_url = ""
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence=page_rule["confidence"],
                parser=page_rule["parser"],
            )
        )
    return records


def fetch_online_html(url: str, timeout_seconds: int = 45) -> tuple[str, str]:
    """使用Windows Schannel在线取得页面，规避站点与Python OpenSSL握手不兼容。"""
    marker = b"\n__CODEX_FINAL_URL__11f5b3e8:"
    command = [
        "curl.exe",
        "--location",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout_seconds),
        "--write-out",
        marker.decode("ascii") + "%{url_effective}",
        url,
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl Schannel在线采集失败（退出码{completed.returncode}）：{error}")
    if marker not in completed.stdout:
        raise RuntimeError("curl Schannel在线采集未返回最终网址标记")
    html_bytes, final_url_bytes = completed.stdout.rsplit(marker, 1)
    html = html_bytes.decode("utf-8-sig", errors="strict")
    final_url = final_url_bytes.decode("utf-8", errors="strict").strip() or url
    return html, final_url


def run_site_adapter(project_dir: Path) -> Path:
    """执行当前站点专用在线采集，并复用公共业务源和十三列导出契约。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.runner import (
        build_selector_summary,
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
        safe_filename,
    )

    rule = apply_business_source(dict(PAGE_RULE))
    try:
        html, final_url = fetch_online_html(str(rule["url"]))
        rows = normalize_inline_rows(rule, parse_page(html, final_url, rule))
        if not rows:
            rows = [make_failure_record(rule, "解析结果为空")]
    except Exception as error:
        rows = [make_failure_record(rule, str(error))]

    normalize_record_source_urls(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        if not row.script_sequence:
            row.script_sequence = normalize_script_sequence(rule["rule_id"])
        if not row.selector_summary:
            row.selector_summary = build_selector_summary(rule)

    output_name = (
        f"{rule['rule_id']}_{safe_filename(rule['page_type'])}_"
        f"{safe_filename(rule['load_mode'])}_{safe_filename(rule['organization'])}.txt"
    )
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, rows)
    return output_path


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    output_path = run_site_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
