from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests


PAGE_RULE = {
    "rule_id": "0898", "page_type": "人物列表完整页", "structure_group": "harbin_common_search_title_duty_api",
    "reuse_scope": "page_structure", "load_mode": "动态JSON接口", "fetch_mode": "requests",
    "extract_mode": "json_api", "collector": "json_api", "parser": "builtin_parse_page",
    "leader_region_selector": "", "name_selector": "title冒号前", "duty_selector": "title冒号后",
    "detail_link_selector": "url", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "api_item_url", "max_detail_links": 50},
    "api": {"endpoint_path": "/common/search/{channel_id}", "channel_id": "e4a21fb12e2346f1b21910241cda011b"},
    "risk_flag": "接口首条为聚合总览，仅接受标题严格符合姓名冒号职务的独立人物项",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    text = html_lib.unescape(html_lib.unescape(str(value or ""))).replace("\u3000", " ")
    return re.sub(r"[\s\xa0\u2000-\u200b]+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    parts = urlsplit(final_url or str(page_rule["url"]))
    channel_id = str(page_rule["api"]["channel_id"])
    query = urlencode({"_isAgg": "false", "_isJson": "true", "_pageSize": "50", "_template": "index",
                       "_rangeTimeGte": "", "_channelName": "", "page": "1"})
    api_url = urlunsplit((parts.scheme, parts.netloc, f"/common/search/{channel_id}", query, ""))
    response = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0", "Referer": f"{parts.scheme}://{parts.netloc}/"}, timeout=30)
    response.raise_for_status()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in response.json().get("data", {}).get("results", []):
        title = clean_text(item.get("title", ""))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff· ]{2,12})[：:](?P<duty>.+)", title)
        if not match:
            continue
        name = match.group("name").replace(" ", "")
        duty = clean_text(match.group("duty"))
        detail_url = str(item.get("url") or "").strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
                     "selector_summary": f"common/search/{channel_id}独立人物title姓名职务及url字段"})
        seen.add(name)
    if not rows:
        raise ValueError("领导JSON接口未返回可验证的独立人物记录")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
