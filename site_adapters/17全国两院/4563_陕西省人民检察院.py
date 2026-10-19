from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4563", "page_type": "省检察院领导动态接口页",
    "structure_group": "shaanxi_procuratorate_leader_api_v1", "reuse_scope": "single_page",
    "load_mode": "JSON接口", "extract_mode": "custom", "parser": "page_shaanxi_procuratorate_leader_api_v1",
    "leader_region_selector": "/api/blade-backend/block/show/leader-info/list?status=0&domainName=shanxi",
    "name_selector": "data[].leaderName", "duty_selector": "data[].position", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "risk_flag": "接口数组原序输出；检察委员会委员、专职委员等委员类人物及职务完整保留。",
}


def compact(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    api_url = "https://www.sn.jcy.gov.cn/api/blade-backend/block/show/leader-info/list?status=0&domainName=shanxi"
    response = requests.get(api_url, timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0", "Referer": str(page_rule["url"])})
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("陕西省检察院领导接口未返回data数组")
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = compact(item.get("leaderName"))
        position = compact(item.get("position")).replace("、纪检监察组", "纪检监察组")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or not position:
            continue
        organization = str(page_rule.get("organization") or "")
        evidence = position if not organization or position.startswith(organization) else organization + position
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "leader-info接口data数组；leaderName/position；包含委员及专职委员"})
    if not rows:
        raise RuntimeError("未提取到省院领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
