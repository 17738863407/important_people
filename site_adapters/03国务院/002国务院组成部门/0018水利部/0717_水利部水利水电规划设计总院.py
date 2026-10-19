from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0717",
    "page_type": "人物列表完整页",
    "structure_group": "giwp_leader_api_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "giwp_leader_api_v2",
    "leader_region_selector": ".portal-leader-main",
    "name_selector": ".portal-leader-item-text-name",
    "duty_selector": ".portal-leader-item-text-name",
    "detail_link_selector": "",
    "api": {
        "endpoint": "/model/data/get",
        "method": "GET",
        "params": {"type": "Leader"},
        "data_path": "data",
        "combined_field": "name",
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "接口name字段合并职务姓名；ll字段为个人简介，不得作为职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """调用页面同源领导接口，并按接口数组顺序拆分职务与姓名。"""
    import requests

    from crawler_core.models import PersonRecord

    api_rule = page_rule["api"]
    entry_url = final_url or page_rule["url"]
    api_url = urljoin(entry_url, api_rule["endpoint"])
    response = requests.get(
        api_url,
        params=api_rule["params"],
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": entry_url,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 200 or not isinstance(payload.get("data"), list):
        raise RuntimeError("领导接口未返回有效data数组")

    records: list[object] = []
    seen: set[str] = set()
    for item in payload[api_rule["data_path"]]:
        if not isinstance(item, dict):
            continue
        label = _clean_text(str(item.get(api_rule["combined_field"]) or ""))
        match = re.fullmatch(
            r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,20})",
            label,
        )
        if match is None:
            continue
        duty = _clean_text(match.group("duty")).replace(" 、", "、").replace("、 ", "、")
        name = re.sub(r"\s+", "", match.group("name"))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
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
