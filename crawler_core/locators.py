from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawler_core.detail_links import parse_detail_chain_records
from crawler_core.llm_vision import parse_llm_vision_records
from crawler_core.models import PersonRecord


def compact_text(value: object) -> str:
    """压缩文本空白。"""
    return " ".join(str(value or "").split())


def get_locator_strategy(rule: dict[str, Any]) -> str:
    """读取页面定位策略；旧脚本默认按 legacy_css 兼容。"""
    strategy = str(rule.get("locator_strategy") or "").strip()
    if strategy:
        return strategy
    if callable(rule.get("parse_page")):
        return "custom_parse_page"
    return "legacy_css"


def build_legacy_css_locator(rule: dict[str, Any], verified_status: str, behavior_changed: bool) -> dict[str, Any]:
    """把旧 CSS 字段包装为统一 locator 元数据。"""
    return {
        "css": {
            "leader_region_selector": str(rule.get("leader_region_selector", "") or ""),
            "name_selector": str(rule.get("name_selector", "") or ""),
            "duty_selector": str(rule.get("duty_selector", "") or ""),
            "detail_link_selector": str(rule.get("detail_link_selector", "") or ""),
            "content_scope": deepcopy(rule.get("content_scope", {})),
        },
        "api": {
            "enabled": False,
            "reason": "未发现或未配置可复现接口，沿用 CSS/HTML 定位",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": verified_status,
            "behavior_changed": behavior_changed,
        },
    }


def apply_locator_to_legacy_fields(rule: dict[str, Any]) -> dict[str, Any]:
    """把 locator.css 回填到旧字段，保证既有解析器继续可用。"""
    local_rule = dict(rule)
    locator = local_rule.get("locator")
    if not isinstance(locator, dict):
        return local_rule
    css_locator = locator.get("css")
    if not isinstance(css_locator, dict):
        return local_rule
    for field_name in [
        "leader_region_selector",
        "name_selector",
        "duty_selector",
        "detail_link_selector",
        "content_scope",
    ]:
        if field_name in css_locator:
            local_rule[field_name] = css_locator[field_name]
    return local_rule


def selector_summary_from_locator(rule: dict[str, Any]) -> str:
    """生成定位策略摘要，供输出结果追溯。"""
    strategy = get_locator_strategy(rule)
    locator = rule.get("locator") if isinstance(rule.get("locator"), dict) else {}
    parts = [f"strategy={strategy}"]
    if isinstance(locator, dict):
        css_locator = locator.get("css")
        if isinstance(css_locator, dict):
            parts.extend(
                [
                    f"leader={css_locator.get('leader_region_selector', rule.get('leader_region_selector', ''))}",
                    f"name={css_locator.get('name_selector', rule.get('name_selector', ''))}",
                    f"duty={css_locator.get('duty_selector', rule.get('duty_selector', ''))}",
                    f"detail={css_locator.get('detail_link_selector', rule.get('detail_link_selector', ''))}",
                ]
            )
        api_locator = locator.get("api") or rule.get("api")
        if isinstance(api_locator, dict):
            parts.append(f"api_enabled={api_locator.get('enabled', bool(api_locator.get('url')))}")
            if api_locator.get("url"):
                parts.append(f"api_url={api_locator.get('url')}")
            if api_locator.get("data_path"):
                parts.append(f"data_path={api_locator.get('data_path')}")
    return "；".join(compact_text(part) for part in parts if compact_text(part))


def read_nested_value(data: Any, path: str) -> Any:
    """按 data.list 或 data[0].list 风格读取嵌套字段。"""
    text = str(path or "").strip().strip("$.")
    if not text:
        return data
    current = data
    for raw_part in text.replace("[", ".[").split("."):
        part = raw_part.strip()
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            index_text = part[1:-1].strip()
            if not isinstance(current, list):
                return None
            try:
                current = current[int(index_text)]
            except Exception:
                return None
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def make_api_request(api_config: dict[str, Any], page_url: str, timeout_seconds: int) -> requests.Response:
    """复现接口请求，返回原始响应。"""
    api_url = str(api_config.get("url") or "").strip()
    if not api_url:
        raise ValueError("接口配置缺少 api.url")
    absolute_url = urljoin(page_url, api_url)
    method = str(api_config.get("method") or "GET").upper()
    params = api_config.get("params") if isinstance(api_config.get("params"), dict) else {}
    data = api_config.get("data") if isinstance(api_config.get("data"), dict) else None
    headers = api_config.get("headers") if isinstance(api_config.get("headers"), dict) else {}
    if page_url and "Referer" not in headers and "referer" not in {str(key).lower() for key in headers}:
        headers = dict(headers)
        headers["Referer"] = page_url
    if method == "POST":
        response = requests.post(absolute_url, params=params, data=data, headers=headers, timeout=timeout_seconds)
    else:
        response = requests.get(absolute_url, params=params, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    return response


def parse_json_api_records(
    rule: dict[str, Any],
    api_config: dict[str, Any],
    page_url: str,
    timeout_seconds: int,
) -> list[PersonRecord]:
    """按 PAGE_RULE.api 字段映射解析 JSON 接口。"""
    response = make_api_request(api_config, page_url, timeout_seconds)
    data = response.json()
    rows_data = read_nested_value(data, str(api_config.get("data_path") or ""))
    if isinstance(rows_data, dict):
        rows_data = [rows_data]
    if not isinstance(rows_data, list):
        raise ValueError("接口响应无法按 data_path 定位到数组")
    name_field = str(api_config.get("name_field") or "name")
    duty_field = str(api_config.get("duty_field") or "duty")
    detail_field = str(api_config.get("detail_field") or "url")
    records: list[PersonRecord] = []
    for index, item in enumerate(rows_data):
        if not isinstance(item, dict):
            continue
        name = compact_text(read_nested_value(item, name_field))
        duty = compact_text(read_nested_value(item, duty_field))
        detail_url = compact_text(read_nested_value(item, detail_field))
        if detail_url:
            detail_url = urljoin(response.url, detail_url)
        if not name and not duty:
            continue
        evidence = json.dumps(item, ensure_ascii=False)
        records.append(
            PersonRecord(
                organization=str(rule.get("organization", "")),
                url=str(rule.get("url", page_url)),
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=f"JSON接口记录[{index}]：{evidence[:500]}",
                confidence=str(rule.get("confidence", "待人工判定")),
                parser=str(rule.get("parser", "V013_json_leader_api_v1")),
                selector_summary=selector_summary_from_locator(rule),
            )
        )
    return records


def parse_xhr_html_records(
    rule: dict[str, Any],
    api_config: dict[str, Any],
    page_url: str,
    timeout_seconds: int,
    snapshot_path: Path | None,
) -> list[PersonRecord]:
    """请求 XHR HTML 片段后，继续复用注册解析器解析片段。"""
    from crawler_core.parser_registry import parse_with_registered_parser

    response = make_api_request(api_config, page_url, timeout_seconds)
    html = response.text
    fragment_selector = str(api_config.get("fragment_selector") or "").strip()
    if fragment_selector:
        soup = BeautifulSoup(html, "html.parser")
        fragments = soup.select(fragment_selector)
        if fragments:
            html = "\n".join(str(fragment) for fragment in fragments)
    local_rule = apply_locator_to_legacy_fields(rule)
    for field_name in ["name_selector", "duty_selector", "detail_link_selector"]:
        if api_config.get(field_name):
            local_rule[field_name] = api_config[field_name]
    if api_config.get("fragment_selector"):
        local_rule["leader_region_selector"] = api_config["fragment_selector"]
    records = parse_with_registered_parser(local_rule, html, response.url, snapshot_path)
    for row in records:
        row.parser = str(rule.get("parser", "V016_xhr_html_fragment_v1"))
        row.selector_summary = selector_summary_from_locator(rule)
    return records


def parse_records_by_locator_strategy(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    snapshot_path: Path | None,
    timeout_seconds: int,
) -> list[PersonRecord] | None:
    """按定位策略解析；返回 None 表示继续走旧解析器。"""
    strategy = get_locator_strategy(rule)
    detail_strategy = rule.get("detail_strategy")
    detail_required = isinstance(detail_strategy, dict) and bool(detail_strategy.get("required"))
    detail_mode = str(detail_strategy.get("mode") if isinstance(detail_strategy, dict) else "").strip()
    if strategy == "detail_chain" or detail_required or detail_mode == "list_to_detail":
        return parse_detail_chain_records(rule, html, final_url, snapshot_path, timeout_seconds)
    llm_strategy = rule.get("llm_strategy")
    llm_required = isinstance(llm_strategy, dict) and bool(llm_strategy.get("required"))
    if strategy == "llm_vision" or llm_required:
        return parse_llm_vision_records(rule, html, final_url, snapshot_path, timeout_seconds)
    if strategy in {"legacy_css", "css", "xpath", "text_anchor", "table_semantic"}:
        return None
    locator = rule.get("locator") if isinstance(rule.get("locator"), dict) else {}
    api_config = rule.get("api")
    if not isinstance(api_config, dict) and isinstance(locator, dict):
        api_config = locator.get("api")
    if strategy == "json_api":
        if not isinstance(api_config, dict):
            raise ValueError("json_api 策略缺少 api 配置")
        return parse_json_api_records(rule, api_config, final_url or str(rule.get("url", "")), timeout_seconds)
    if strategy == "xhr_html":
        if not isinstance(api_config, dict):
            raise ValueError("xhr_html 策略缺少 api 配置")
        return parse_xhr_html_records(rule, api_config, final_url or str(rule.get("url", "")), timeout_seconds, snapshot_path)
    if strategy == "custom_parse_page":
        return None
    raise ValueError(f"未知 locator_strategy：{strategy}")
