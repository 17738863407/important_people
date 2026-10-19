from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0963",
    "page_type": "人物列表完整页",
    "structure_group": "huhhot_cppcc_leadership_json_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "huhhot_cppcc_leadership_json_v1",
    "leader_region_selector": "section.leaders-preview div#leaderCards",
    "name_selector": "JSON 分组数组[].name",
    "duty_selector": "JSON 分组数组[].fullPosition",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "api": {
        "enabled": True,
        "endpoint": "https://www.hhhtzx.gov.cn/api/politicalConsultativeLeadership/list",
        "method": "GET",
        "data_path": "根对象各分组数组",
        "name_field": "name",
        "duty_field": "fullPosition",
        "order_field": "order",
        "status_field": "status",
    },
    "risk_flag": "入口HTML仅为前端骨架；人物数据由同站公开JSON接口加载",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: object) -> str:
    """仅合并接口字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在线读取领导接口，并按接口显式order字段输出当前启用人物。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    api = page_rule["api"]
    result = fetch_html_with_strategy(str(api["endpoint"]), strategy="requests", timeout=60)
    payload = json.loads(result.html)
    if not isinstance(payload, dict):
        raise RuntimeError("领导接口根节点不是分组对象")

    items: list[dict] = []
    for group in payload.values():
        if not isinstance(group, list):
            raise RuntimeError("领导接口分组不是数组")
        for item in group:
            if isinstance(item, dict) and int(item.get(api["status_field"], 0)) == 1:
                items.append(item)
    items.sort(key=lambda item: int(item.get(api["order_field"], 999999)))

    records: list[object] = []
    seen_names: set[str] = set()
    for item in items:
        name = _clean_text(item.get(api["name_field"])).replace(" ", "")
        evidence = _clean_text(item.get(api["duty_field"]))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("领导接口存在无效姓名或空职务字段")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )

    if not records:
        raise RuntimeError("领导接口没有当前启用人物")
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
