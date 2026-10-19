from __future__ import annotations

import re
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
    "rule_id": "3674", "page_type": "定义列表职务人物链接页",
    "structure_group": "chd_leader_definition_lists_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出（HTTPS握手超时，使用同域HTTP）", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "raw_http", "parser": "chd_leader_definition_lists_v1",
    "leader_region_selector": ".n_left.xrld", "name_selector": "dl.list17 dd a[href]",
    "duty_selector": "dl.list17 dt", "detail_link_selector": "dl.list17 dd a[href]",
    "content_scope": {"include_selectors": [".n_left.xrld"], "exclude_selectors": ["dl[style*='display:none']"]},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "主表HTTPS入口握手持续超时，同域HTTP返回权威页面；含空纪委书记组和隐藏校长助理组",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐个可见定义列表读取职务与人物，并按首次出现顺序聚合。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".n_left.xrld")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for group in region.select("dl.list17"):
        if "display:none" in str(group.get("style", "")).replace(" ", "").lower():
            continue
        duty_node = group.select_one("dt")
        duty = _compact(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for anchor in group.select("dd a[href]"):
            name = _compact(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            if duty not in person["duties"]:
                person["duties"].append(duty)
            if not person["detail_url"]:
                person["detail_url"] = detail_url
    return [PersonRecord(
        organization=page_rule["organization"], url=page_rule["url"], name=name,
        duty="；".join(data["duties"]), detail_url=data["detail_url"], evidence="；".join(data["duties"]),
        confidence="high", parser=page_rule["parser"], selector_summary=".n_left.xrld内可见dl.list17的dt与人物链接",
    ) for name, data in people.items()]


def run_adapter(project_dir: Path, update_fetch_memory: bool) -> Path:
    """在不写采集器记忆的前提下，经同域HTTP采集并按公共契约导出。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        apply_business_location,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    if update_fetch_memory:
        raise ValueError("本任务禁止更新采集器记忆")
    rule = apply_business_source(dict(PAGE_RULE))
    fetch_url = re.sub(r"^https://", "http://", str(rule["url"]), count=1, flags=re.IGNORECASE)
    fetched = fetch_html_with_strategy(fetch_url, strategy="raw_http", timeout=45)
    rows = normalize_inline_rows(rule, parse_page(fetched.html, fetched.final_url, rule))
    if not rows:
        raise RuntimeError("同域HTTP页面未解析出有效领导记录")
    normalize_record_source_urls(rule, rows)
    apply_business_location(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(rule["rule_id"])
    output_path = project_dir / "outputs" / build_output_name(rule["rule_id"], rule["organization"])
    export_records(output_path, rows)
    return output_path


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    output_path = run_adapter(project_dir, update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
