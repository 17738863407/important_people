from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0918",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_leader_channel_json_content",
    "reuse_scope": "page_structure",
    "load_mode": "动态JSON接口",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "json_api",
    "parser": "builtin_parse_page",
    "leader_region_selector": "领导频道接口results数组",
    "name_selector": "content段首冒号前姓名",
    "duty_selector": "content冒号后首句",
    "detail_link_selector": "results.url",
    "channel_id": "998f5ab62b8242758bbc6b5f1b32fc4b",
    "search_path_prefix": "/common/search/",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "api_url", "max_detail_links": 50},
    "risk_flag": "由规则入口站点基址动态构造领导频道接口，按数组顺序解析当前结果",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    decoded = html_lib.unescape(str(value or ""))
    plain = BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True) if "<" in decoded and ">" in decoded else decoded
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", plain).strip()
    return re.sub(r"\s*([：:，,。；])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    entry_url = str(page_rule.get("url") or final_url or "")
    parts = urlsplit(entry_url)
    if not parts.scheme or not parts.netloc:
        raise ValueError("规则主表入口网址缺少有效站点基址")
    base_url = f"{parts.scheme}://{parts.netloc}"
    api_url = urljoin(base_url, page_rule["search_path_prefix"] + page_rule["channel_id"])
    response = requests.get(
        api_url,
        params={
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "50",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Referer": base_url + "/"},
    )
    response.raise_for_status()
    results = response.json().get("data", {}).get("results", [])
    rows: list[dict[str, str]] = []
    for item in results:
        content = clean_text(item.get("content", ""))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff· ]{2,8})[：:](?P<duty>[^。；]+)[。；]", content)
        if not match:
            raise ValueError("领导频道接口记录缺少可验证的姓名职务首句")
        name = clean_text(match.group("name")).replace(" ", "")
        duty = clean_text(match.group("duty"))
        detail_url = urljoin(base_url, clean_text(item.get("url", ""))) if item.get("url") else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "领导频道接口results.content首句及url字段",
            }
        )
    if not rows:
        raise ValueError("领导频道接口未返回人物记录")
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
