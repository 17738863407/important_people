from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2470",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_json",
    "parser": "anhui_public_info_leader_api_v3",
    "leader_region_selector": "#xxgk_lmcon",
    "name_selector": "json:data[].title首段",
    "duty_selector": "json:data[].title余段",
    "detail_link_selector": "json:data[].link",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "入口HTML列表为空，必须按catIds调用站点公开信息JSON接口",
    "api": {
        "endpoint": "/site/label/8888",
        "method": "GET",
        "params": {
            "labelName": "publicInfoList",
            "siteId": "31402941",
            "organId": "7061",
            "pageSize": "20",
            "pageIndex": "1",
            "isDate": "true",
            "dateFormat": "yyyy-MM-dd",
            "length": "50",
            "type": "4",
            "action": "list",
            "result": "",
            "isJson": "true",
            "keyWords": "",
            "isRel": "true",
            "catIds": "34482268",
        },
        "data_path": "data",
        "title_field": "title",
        "detail_field": "link",
    },
}


def _clean_text(value: object) -> str:
    """仅清理接口字段中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """调用页面声明的稳定JSON接口，并继承接口数组顺序。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    api_rule = page_rule["api"]
    endpoint = urljoin(final_url, api_rule["endpoint"])
    api_url = f"{endpoint}?{urlencode(api_rule['params'])}"
    response = fetch_html_with_strategy(api_url, "raw_http")
    payload = json.loads(response.html)
    items = payload.get(api_rule["data_path"], [])
    if not isinstance(items, list):
        return []

    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get(api_rule["title_field"]))
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,8})\s+(.{2,80})", title)
        if match is None:
            continue
        name, duty = match.groups()
        duty = _clean_text(duty)
        if name in seen_names or not duty:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, _clean_text(item.get(api_rule["detail_field"])))
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


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
