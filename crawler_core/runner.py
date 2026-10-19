from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crawler_core.business_sources import apply_business_source, normalize_script_sequence
from crawler_core.exporter import export_records
from crawler_core.fetch_memory import load_fetch_memory, preferred_fetch_mode, record_fetch_success
from crawler_core.fetcher import (
    FetchResult,
    disable_unavailable_loopback_proxies,
    extract_javascript_location_redirect,
    fetch_by_raw_requests,
    fetch_html_with_preferred_fallback,
    fetch_html_with_strategy,
    rendered_html_issue,
)
from crawler_core.locators import apply_locator_to_legacy_fields, parse_records_by_locator_strategy, selector_summary_from_locator
from crawler_core.parsers import parse_generic_confirmed_page
from crawler_core.parser_registry import parse_with_registered_parser
from crawler_core.models import PersonRecord
from crawler_core.naming import build_output_name
from crawler_core.settings import get_settings
from crawler_core.snapshots import build_snapshot_path, make_snapshot_fetch_result


def load_rules(v3_dir: Path) -> list[dict[str, Any]]:
    """读取 V3 页面级规则。"""
    path = v3_dir / "data" / "已通过页面规则.jsonl"
    rules: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            rule = json.loads(line)
            rules.append(rule)
    return rules


def run_page_by_rule(rule: dict[str, Any], output_dir: Path | None = None) -> Path:
    """按脚本内嵌页面规则采集，默认读取本地快照。"""
    rule = apply_business_source(rule)
    v3_dir = Path(__file__).resolve().parents[1]
    sequence = str(rule.get("sequence", "")).zfill(4)
    organization = str(rule.get("organization", "页面"))
    fetch_result, snapshot_path = fetch_html_for_rule(rule, v3_dir)
    html = fetch_result.html
    final_url = fetch_result.final_url
    rule["final_url"] = final_url
    rows = parse_generic_confirmed_page(rule, html, snapshot_path, final_url)
    apply_business_location(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.adapter_script = str(rule.get("adapter_script", ""))
        row.selector_summary = build_selector_summary(rule)
    target_dir = output_dir or (v3_dir / "outputs")
    output_path = target_dir / build_output_name(sequence, organization)
    export_records(output_path, rows)
    return output_path


def run_all_pages() -> Path:
    """运行全部已通过页面级脚本对应规则。"""
    v3_dir = Path(__file__).resolve().parents[1]
    rules = load_rules(v3_dir)
    for rule in rules:
        output_path = run_page_by_rule(rule)
        # 单页结果已经落盘；汇总读取不是必须，保持主流程简单稳定。
        print(f"已完成：{output_path.name} -> {output_path}")
    return v3_dir / "outputs"


def resolve_adapter_script(
    project_dir: Path,
    adapter_globals: dict[str, Any] | None,
    fallback: object = "",
) -> str:
    """根据实际执行文件生成项目内相对路径，避免页面脚本保存易失效的路径常量。"""
    script_file = (adapter_globals or {}).get("__file__")
    if not script_file:
        return str(fallback or "")

    script_path = Path(str(script_file)).resolve()
    try:
        relative_path = script_path.relative_to(project_dir.resolve())
    except ValueError:
        return str(fallback or "")
    return str(relative_path).replace("/", "\\")


def normalize_inline_rows(rule: dict[str, Any], rows: list[dict[str, Any] | PersonRecord]) -> list[PersonRecord]:
    """将脚本内置 parse_page 返回的 dict 规范为 PersonRecord。"""
    records: list[PersonRecord] = []
    for row in rows:
        if isinstance(row, PersonRecord):
            records.append(row)
            continue
        records.append(
            PersonRecord(
                organization=str(row.get("organization", rule.get("organization", ""))),
                url=str(row.get("url", rule.get("url", ""))),
                name=str(row.get("name", "")),
                duty=str(row.get("duty", "")),
                detail_url=str(row.get("detail_url", "")),
                evidence=str(row.get("evidence", "")),
                confidence=str(row.get("confidence", rule.get("confidence", "待人工判定"))),
                parser=str(row.get("parser", rule.get("parser", ""))),
                snapshot_path=str(row.get("snapshot_path", "")),
                adapter_script=str(row.get("adapter_script", rule.get("adapter_script", ""))),
                selector_summary=str(row.get("selector_summary", build_selector_summary(rule))),
                order=str(row.get("order", "")),
                sort_order=str(row.get("sort_order", "")),
                rank=str(row.get("rank", "")),
                province=str(row.get("province", "")),
                city=str(row.get("city", "")),
                maintainer=str(row.get("maintainer", "")),
                script_sequence=normalize_script_sequence(
                    row.get("script_sequence", rule.get("rule_id") or rule.get("sequence"))
                ),
            )
        )
    return records


def build_selector_summary(rule: dict[str, Any]) -> str:
    """生成输出用选择器摘要。"""
    if rule.get("locator_strategy") or isinstance(rule.get("locator"), dict):
        return selector_summary_from_locator(rule)
    parts = [
        f"leader={rule.get('leader_region_selector', '')}",
        f"name={rule.get('name_selector', '')}",
        f"duty={rule.get('duty_selector', '')}",
        f"detail={rule.get('detail_link_selector', '')}",
    ]
    return "；".join(parts)


def make_failure_record(rule: dict[str, Any], reason: str) -> PersonRecord:
    """构造失败记录，保证失败时也输出 TXT。"""
    return PersonRecord(
        organization=str(rule.get("organization", "")),
        url=str(rule.get("url", "")),
        name="",
        duty="",
        detail_url="",
        evidence=f"抽取失败：{reason}",
        confidence=str(rule.get("confidence", "失败")),
        parser=str(rule.get("parser", "")),
        selector_summary=build_selector_summary(rule),
    )


def normalize_record_source_urls(rule: dict[str, Any], rows: list[PersonRecord]) -> None:
    """统一保证输出中的“网址”列为脚本 PAGE_RULE 机构网址。"""
    source_url = str(rule.get("url", "")).strip()
    if not source_url:
        return
    for row in rows:
        current_url = str(row.url or "").strip()
        if current_url and current_url != source_url and not row.detail_url:
            row.detail_url = current_url
        row.url = source_url


def prepare_records_for_export(rows: list[PersonRecord]) -> None:
    """将旧解析器职务转存为原始证据，并冻结规范职务为空。"""
    for row in rows:
        original_duty = str(row.duty or "").strip()
        if row.name and original_duty and original_duty not in str(row.evidence or ""):
            row.evidence = original_duty
        row.duty = ""


def apply_business_location(rule: dict[str, Any], rows: list[PersonRecord]) -> None:
    """用规则主表中的机构级地区统一覆盖人物记录地区。"""
    province = str(rule.get("province", "")).strip()
    city = str(rule.get("city", "")).strip()
    for row in rows:
        row.province = province
        row.city = city


def apply_remembered_fetch_mode(rule: dict[str, Any], project_dir: Path) -> None:
    """忽略页面脚本历史配置，并把最近成功采集器设为首选而非唯一方式。"""
    if rule.get("_fetch_mode_override"):
        return
    rule.pop("fetch_mode", None)
    rule.pop("preferred_fetch_mode", None)
    nested_fetch = rule.get("fetch")
    if isinstance(nested_fetch, dict):
        nested_fetch = dict(nested_fetch)
        nested_fetch.pop("mode", None)
        rule["fetch"] = nested_fetch

    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
    memory_path = project_dir / "workspace" / "module" / "采集方式成功记录.txt"
    if not sequence or not memory_path.is_file():
        return
    record = load_fetch_memory(memory_path).get(sequence)
    remembered_mode = preferred_fetch_mode(record)
    if remembered_mode:
        rule["_remembered_fetch_mode"] = remembered_mode


def fetch_html_for_rule(rule: dict[str, Any], project_dir: Path, timeout_seconds: int | None = None) -> tuple[Any, Path | None]:
    """按配置读取本地快照或在线采集。"""
    settings = get_settings()
    if bool(rule.get("inline_parser_handles_fetch")):
        collector = str(rule.get("inline_fetch_collector") or "").strip().lower()
        if collector not in {"raw_http", "requests", "playwright", "chrome_cdp"}:
            raise ValueError(f"内置解析器采集器无效：{collector or '未配置'}")
        return (
            FetchResult(
                html="",
                final_url=str(rule["url"]),
                collector=collector,
                warnings=["入口预抓取已跳过：由页面内置解析器自行采集权威数据源"],
                attempted_collectors=[f"{collector}(inline_parser):执行"],
            ),
            None,
        )
    mode = str(rule.get("fetch_mode") or settings.default_fetch_mode).strip().lower()
    remembered_mode = str(rule.get("_remembered_fetch_mode") or "").strip().lower()
    browser_render_wait_ms = max(
        0,
        int(rule.get("browser_render_wait_ms") or settings.browser_render_wait_ms),
    )
    if remembered_mode and not rule.get("_fetch_mode_override"):
        return fetch_html_with_preferred_fallback(
            str(rule["url"]),
            preferred_strategy=remembered_mode,
            timeout=timeout_seconds or settings.request_timeout_seconds,
            request_attempt_offset=int(rule.get("requests_attempt_offset") or 0),
            playwright_stealth_profile=int(rule.get("playwright_stealth_profile") or 1),
            browser_render_wait_ms=browser_render_wait_ms,
        ), None
    if mode == "snapshot":
        snapshot_path = build_snapshot_path(project_dir, rule)
        return make_snapshot_fetch_result(rule, project_dir), snapshot_path
    if mode == "raw_http":
        return fetch_by_raw_requests(
            str(rule["url"]),
            timeout=timeout_seconds or settings.request_timeout_seconds,
            attempt_offset=int(rule.get("requests_attempt_offset") or 0),
        ), None
    if mode == "llm_vision":
        return fetch_html_with_strategy(
            str(rule["url"]),
            strategy="requests",
            timeout=timeout_seconds,
            request_attempt_offset=int(rule.get("requests_attempt_offset") or 0),
        ), None
    if mode in {"requests", "playwright", "chrome", "chrome_cdp"}:
        return fetch_html_with_strategy(
            str(rule["url"]),
            strategy=mode,
            timeout=timeout_seconds,
            request_attempt_offset=int(rule.get("requests_attempt_offset") or 0),
            playwright_stealth_profile=int(rule.get("playwright_stealth_profile") or 1),
            browser_render_wait_ms=browser_render_wait_ms,
        ), None

    force_browser = bool(rule.get("force_browser")) or str(rule.get("load_mode", "")) in {
        "动态DOM渲染",
        "iframe嵌入",
        "接口数据加载",
        "动态XHR返回HTML片段",
        "动态JSON接口",
    }
    fetch_result = fetch_html_with_strategy(
        str(rule["url"]),
        strategy="extract",
        force_browser=force_browser,
        timeout=timeout_seconds,
        request_attempt_offset=int(rule.get("requests_attempt_offset") or 0),
        playwright_stealth_profile=int(rule.get("playwright_stealth_profile") or 1),
        browser_render_wait_ms=browser_render_wait_ms,
    )
    return fetch_result, None


def run_page_adapter(
    rule: dict[str, Any],
    adapter_globals: dict[str, Any] | None = None,
    output_dir: Path | None = None,
    runtime_context: dict[str, Any] | None = None,
    update_fetch_memory: bool = True,
) -> Path:
    """运行新方案页面级爬虫脚本。

    页面脚本可提供 parse_page(html, final_url, page_rule)，存在时优先调用；
    否则使用 parser_registry 中的版本化解析器。
    """
    rule = apply_business_source(rule)
    project_dir = Path(__file__).resolve().parents[1]
    disabled_proxy_variables = disable_unavailable_loopback_proxies()
    apply_remembered_fetch_mode(rule, project_dir)
    if runtime_context is not None:
        runtime_context.clear()
        runtime_context.update(
            {
                "scheduled_mode": str(rule.get("fetch_mode") or get_settings().default_fetch_mode),
                "actual_collector": "",
                "execution_mode": "",
                "attempted_collectors": [],
                "fetch_succeeded": False,
                "extraction_succeeded": False,
                "error": "",
                "disabled_proxy_variables": disabled_proxy_variables,
            }
        )
    rule["adapter_script"] = resolve_adapter_script(
        project_dir=project_dir,
        adapter_globals=adapter_globals,
        fallback=rule.get("adapter_script", ""),
    )
    rule_id = str(rule.get("rule_id") or rule.get("sequence") or "").zfill(4)
    organization = str(rule.get("organization", "页面"))
    try:
        fetch_result, snapshot_path = fetch_html_for_rule(rule, project_dir)
        html = fetch_result.html
        final_url = fetch_result.final_url
        rule["final_url"] = final_url
        rule["fetch_collector"] = str(getattr(fetch_result, "collector", ""))
        rule["fetch_execution_mode"] = str(getattr(fetch_result, "execution_mode", ""))
        rule["fetch_attempted_collectors"] = list(getattr(fetch_result, "attempted_collectors", []) or [])
        rule["fetch_status_code"] = str(getattr(fetch_result, "status_code", ""))
        rule["fetch_content_type"] = str(getattr(fetch_result, "content_type", ""))
        if runtime_context is not None:
            runtime_context.update(
                {
                    "actual_collector": str(getattr(fetch_result, "collector", "")),
                    "execution_mode": str(getattr(fetch_result, "execution_mode", "")),
                    "attempted_collectors": list(getattr(fetch_result, "attempted_collectors", []) or []),
                    "fetch_succeeded": True,
                    "status_code": str(getattr(fetch_result, "status_code", "")),
                    "content_type": str(getattr(fetch_result, "content_type", "")),
                    "final_url": final_url,
                    "has_javascript_redirect": bool(extract_javascript_location_redirect(html)),
                    "page_issue": rendered_html_issue(html),
                }
            )
        inline_parser = (adapter_globals or {}).get("parse_page")
        if callable(inline_parser):
            rows = normalize_inline_rows(rule, inline_parser(html, final_url, rule))
        else:
            locator_rows = parse_records_by_locator_strategy(
                rule,
                html,
                final_url,
                snapshot_path,
                timeout_seconds=get_settings().request_timeout_seconds,
            )
            should_fallback_to_parser = locator_rows is None
            if locator_rows == [] and str(rule.get("parser") or "").strip():
                should_fallback_to_parser = str(rule.get("locator_strategy") or "").strip().lower() != "llm_vision"
            if should_fallback_to_parser:
                rows = parse_with_registered_parser(apply_locator_to_legacy_fields(rule), html, final_url, snapshot_path)
            else:
                rows = locator_rows
        if not rows:
            rows = [make_failure_record(rule, "解析结果为空")]
    except Exception as error:
        if runtime_context is not None:
            runtime_context["error"] = str(error)
        rows = [make_failure_record(rule, str(error))]
    extraction_succeeded = bool(rows) and any(str(row.name or "").strip() for row in rows) and not any(
        str(row.evidence or "").strip().startswith("抽取失败") for row in rows
    )
    if runtime_context is not None:
        runtime_context["extraction_succeeded"] = extraction_succeeded
        if bool(rule.get("inline_parser_handles_fetch")):
            inline_collector = str(rule.get("inline_fetch_collector") or "").strip().lower()
            inline_status = "成功" if extraction_succeeded else "失败"
            runtime_context["attempted_collectors"] = [
                f"{inline_collector}(inline_parser):{inline_status}"
            ]
    normalize_record_source_urls(rule, rows)
    apply_business_location(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.adapter_script = str(rule.get("adapter_script", ""))
        if not row.script_sequence:
            row.script_sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
        if not row.selector_summary:
            row.selector_summary = build_selector_summary(rule)
    target_dir = output_dir or (project_dir / "outputs")
    output_name = build_output_name(rule_id, organization)
    output_path = target_dir / output_name
    export_records(output_path, rows)
    if runtime_context is not None:
        runtime_context["output_path"] = str(output_path)
    if update_fetch_memory and extraction_succeeded:
        actual_collector = str((runtime_context or {}).get("actual_collector") or rule.get("fetch_collector") or "")
        execution_mode = str(
            (runtime_context or {}).get("execution_mode") or rule.get("fetch_execution_mode") or ""
        )
        record_fetch_success(
            project_dir / "workspace" / "module" / "采集方式成功记录.txt",
            rule_id,
            actual_collector,
            execution_mode,
        )
    return output_path
