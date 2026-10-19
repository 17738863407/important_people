from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0059",
    "page_type": "集团领导JSON接口",
    "structure_group": "class_group_profile_api",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "api_direct",
    "collector": "custom_api_http",
    "parser": "page_class_group_profile_api_v1",
    "leader_region_selector": "api:/admin/frontend/column-content/list",
    "name_selector": "json.data[*].name",
    "duty_selector": "json.data[*].title",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口页为Vue空壳，必须动态发现“集团领导”栏目ID后读取领导接口",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "column_endpoint": "/admin/frontend/column-content/list",
            "leader_endpoint": "/admin/frontend/column-content/getPageList",
            "method": "GET",
            "column_name": "集团领导",
            "column_data_path": "data",
            "leader_data_path": "data",
            "column_id_parameter": "columnId",
            "name_field": "name",
            "duty_field": "title",
        }
    },
}


def clean_text(value: object) -> str:
    """压缩接口字段中的全角空格与其他排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", str(value or "")).strip()


def request_json(session: requests.Session, url: str, referer: str) -> dict[str, object]:
    """读取官方JSON接口，并校验HTTP状态和顶层业务状态。"""
    response = session.get(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": referer,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError(f"官方接口返回异常：{payload!r}")
    return payload


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态发现集团领导栏目并按接口原始顺序提取人物。"""
    source_url = str(page_rule.get("url") or final_url or "")
    parsed = urlsplit(source_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("规则主表中的领导链接无效")

    api_config = dict(page_rule.get("locator", {}).get("api", {}))
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    session = requests.Session()
    session.trust_env = False

    column_payload = request_json(
        session,
        base_url + str(api_config["column_endpoint"]),
        source_url,
    )
    columns = column_payload.get(str(api_config["column_data_path"]))
    if not isinstance(columns, list):
        raise RuntimeError("栏目接口未返回有效数组")

    target_column = next(
        (
            item
            for item in columns
            if isinstance(item, dict)
            and clean_text(item.get("name")) == str(api_config["column_name"])
        ),
        None,
    )
    if not target_column or not target_column.get("id"):
        raise RuntimeError("未在栏目接口中找到“集团领导”")

    leader_response = session.get(
        base_url + str(api_config["leader_endpoint"]),
        params={str(api_config["column_id_parameter"]): target_column["id"]},
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": source_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0",
        },
        timeout=30,
    )
    leader_response.raise_for_status()
    leader_payload = leader_response.json()
    if not isinstance(leader_payload, dict) or leader_payload.get("code") != 0:
        raise RuntimeError(f"集团领导接口返回异常：{leader_payload!r}")
    leaders = leader_payload.get(str(api_config["leader_data_path"]))
    if not isinstance(leaders, list):
        raise RuntimeError("集团领导接口未返回有效数组")

    rows: list[dict[str, str]] = []
    for item in leaders:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get(str(api_config["name_field"]))).replace(" ", "")
        duty = clean_text(item.get(str(api_config["duty_field"])))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                }
            )
    if not rows:
        raise RuntimeError("集团领导接口未提取到有效人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
