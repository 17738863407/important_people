from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2240",
    "page_type": "API人物列表",
    "structure_group": "sichuan_tobacco_leader_api",
    "reuse_scope": "single_page",
    "load_mode": "API接口",
    "fetch_mode": "raw_http",
    "extract_mode": "api_json",
    "collector": "static_http",
    "parser": "custom_sichuan_tobacco_leader_api_v1",
    "leader_region_selector": "#lingdaoxinxi",
    "name_selector": ".leader .name",
    "duty_selector": ".leader .position",
    "detail_link_selector": "#lingdaoxinxi a[href]",
    "api_endpoint": "/province_api/mobile/leader/list",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#lingdaoxinxi"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": "#lingdaoxinxi a[href]",
        "detail_name_selector": ".leaderinfo .name",
        "detail_duty_selector": ".leaderinfo .position",
        "detail_content_selector": ".leaderinfo",
        "max_detail_links": 50,
    },
    "risk_flag": "浏览器访问受站点防护拦截；使用前端公开、无需动态令牌的领导JSON接口",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "api",
    "locator": {
        "css": {
            "leader_region_selector": "#lingdaoxinxi",
            "name_selector": ".leader .name",
            "duty_selector": ".leader .position",
            "detail_link_selector": "#lingdaoxinxi a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["#lingdaoxinxi"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": True,
            "endpoint": "/province_api/mobile/leader/list",
            "method": "GET",
            "data_path": "result[]及其children[]",
            "field_mapping": {
                "name": "name",
                "duty": "position",
                "detail_id": "id",
                "order": "父项数组顺序后接children数组顺序",
            },
        },
    },
}


def _clean_name(value: object) -> str:
    """清理接口为二字姓名插入的排版空格。"""
    return re.sub(r"\s+", "", str(value or ""))


def _iter_visible_leaders(payload: object):
    """按接口父项、子项的原始数组顺序展开当前显示人物。"""
    if not isinstance(payload, list):
        return
    for parent in payload:
        if not isinstance(parent, dict):
            continue
        yield parent
        children = parent.get("children")
        if isinstance(children, list):
            yield from (child for child in children if isinstance(child, dict))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """调用站点前端使用的公开领导接口并解析当前显示人物。"""
    source_url = str(page_rule.get("url", final_url))
    api_url = urljoin(source_url, str(page_rule["api_endpoint"]))
    response = requests.get(
        api_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": source_url,
            "Content-Type": "application/json",
            "token": "token",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200 or not payload.get("success"):
        raise RuntimeError(f"领导接口返回失败：{payload.get('message', '未知错误')}")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in _iter_visible_leaders(payload.get("result")):
        if item.get("showFlag") is False or item.get("delFlag") is True:
            continue
        name = _clean_name(item.get("name"))
        duty = " ".join(str(item.get("position") or "").split())
        detail_id = str(item.get("id") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = ""
        if re.fullmatch(r"[0-9a-fA-F]{32}", detail_id):
            detail_url = urljoin(source_url, f"/cygk/leaderinfo/{detail_id}")

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_sichuan_tobacco_leader_api_v1",
                "selector_summary": "GET /province_api/mobile/leader/list；result及children原序",
            }
        )

    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
