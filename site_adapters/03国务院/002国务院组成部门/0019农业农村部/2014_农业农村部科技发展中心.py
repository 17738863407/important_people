from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2014",
    "domain": "www.nybkjfzzx.cn",
    "page_type": "人物列表完整页",
    "structure_group": "nybkjfzzx_getld_html_fragment",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nybkjfzzx_getld_v1",
    "leader_region_selector": ".ldjj2",
    "name_selector": ".ns span",
    "duty_selector": ".ldjj4",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".ldjj2"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "入口页仅声明GetLD(11)，现任领导数据必须由稳定POST接口在线取得",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldjj2",
            "name_selector": ".ns span",
            "duty_selector": ".ldjj4",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".ldjj2"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": True,
            "endpoint": "/Handler/ArticlesHandler.ashx",
            "method": "POST",
            "form": {"OP": "getld", "ID": "11"},
            "response_type": "html_fragment",
            "item_selector": ".ldjj2",
            "name_field": ".ns span",
            "duty_field": ".ldjj4",
            "pagination": "none",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_api",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理接口HTML片段中的排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def fetch_leader_fragment(final_url: str) -> str:
    """按入口页公开的GetLD(11)调用取得现任领导HTML片段。"""
    endpoint = urljoin(final_url, "/Handler/ArticlesHandler.ashx")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        response = requests.post(
            endpoint,
            data={"OP": "getld", "ID": "11"},
            headers={
                "Referer": final_url,
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
            verify=False,
        )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线请求领导接口，并按接口HTML数组顺序抽取姓名与原始职务。"""
    del html
    if not final_url:
        return []
    try:
        fragment = fetch_leader_fragment(final_url)
    except requests.RequestException:
        return []

    soup = BeautifulSoup(fragment, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；api=POST ArticlesHandler.ashx getld/11；item=.ldjj2"

    for item in soup.select(".ldjj2"):
        name_node = item.select_one(".ns span")
        duty_node = item.select_one(".ldjj4")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
