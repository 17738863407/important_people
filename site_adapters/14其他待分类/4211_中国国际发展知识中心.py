from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4211",
    "page_type": "JavaScript 渲染的接口型中心领导页",
    "load_mode": "JSON 接口",
    "extract_mode": "api_json",
    "parser": "page_inline_cikd_leaders_api_v1",
    "leader_region_selector": "接口菜单“中心领导”",
    "name_selector": "data.list[].contentTitle",
    "duty_selector": "data.list[].contentDescription",
    "detail_link_selector": "data.list[].id",
    "detail_strategy": {"required": False, "mode": "api_document_id"},
    "confidence": "high",
    "filter_policy": "strong_api_structure",
}


def _fetch_json(url: str) -> dict:
    from crawler_core.fetcher import fetch_by_raw_requests

    return json.loads(fetch_by_raw_requests(url).html)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按接口菜单原始顺序逐个读取领导职务栏目，不固化人物或文档 ID。"""
    entry = urlsplit(str(page_rule["url"]))
    menu_id = parse_qs(entry.query).get("menuId", [""])[0]
    if not menu_id:
        return []
    origin = urlunsplit((entry.scheme, entry.netloc, "", "", ""))
    api_root = f"{origin}/ckidfront/CkidIndexController"
    menu_url = f"{api_root}/getAllMenuById?{urlencode({'menuId': menu_id, 'onlyChild': 'false', 'paltformId': ''})}"
    menu_data = _fetch_json(menu_url).get("data") or {}
    rows: list[dict] = []
    for category in menu_data.get("childrenList") or []:
        category_id = str(category.get("id") or "")
        if not category_id:
            continue
        query = urlencode({"menuId": category_id, "pageNum": 1, "pageSize": 100, "isKY": "false"})
        result = _fetch_json(f"{api_root}/docListByMenuId?{query}").get("data") or {}
        for item in result.get("list") or []:
            name = "".join(str(item.get("contentTitle") or "").split())
            duty = " ".join(str(item.get("contentDescription") or "").split())
            document_id = str(item.get("id") or "")
            if not name or not duty:
                continue
            detail_url = f"{origin}/detail?{urlencode({'docId': document_id})}" if document_id else ""
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url})
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
