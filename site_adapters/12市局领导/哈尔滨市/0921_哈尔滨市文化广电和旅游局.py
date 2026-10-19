from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0921",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_individual_leader_api_title_suffix_name",
    "reuse_scope": "page_structure",
    "load_mode": "动态JSON接口",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "json_api",
    "parser": "builtin_parse_page",
    "leader_region_selector": "领导频道接口results数组",
    "name_selector": "content段首姓名",
    "duty_selector": "title末尾姓名前完整职务",
    "detail_link_selector": "results.url",
    "channel_id": "0a11ffdb93554400a2b350017d8cf22e",
    "search_path_prefix": "/common/search/",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "api_url", "max_detail_links": 50},
    "risk_flag": "由content段首姓名反向校验title后缀，排除领导班子汇总文章",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def plain_text(value: str) -> str:
    decoded = html_lib.unescape(str(value or ""))
    if "<" in decoded and ">" in decoded:
        decoded = BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", decoded).strip()


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", plain_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    entry_url = str(page_rule.get("url") or final_url or "")
    parts = urlsplit(entry_url)
    if not parts.scheme or not parts.netloc:
        raise ValueError("规则主表入口网址缺少有效站点基址")
    base_url = f"{parts.scheme}://{parts.netloc}"
    response = requests.get(
        urljoin(base_url, page_rule["search_path_prefix"] + page_rule["channel_id"]),
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
        content = plain_text(item.get("content", ""))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,5})[，,]", content)
        if not name_match:
            continue
        name = name_match.group("name")
        title = compact_text(item.get("title", ""))
        if "领导班子" in title or not title.endswith(name):
            continue
        duty = title[: -len(name)].strip("：:，,。")
        if not duty:
            raise ValueError(f"个人领导接口标题缺少姓名前职务：{name}")
        detail_url = urljoin(base_url, plain_text(item.get("url", ""))) if item.get("url") else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "领导频道接口content段首姓名与title后缀反向校验",
            }
        )
    if not rows:
        raise ValueError("领导频道接口未返回可验证的个人记录")
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
