from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0709",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_ghhzrzy_leader_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_ghhzrzy_leader_details_v1",
    "leader_region_selector": ".ldxx_right",
    "name_selector": "a[href*='/ldxxlm/']",
    "duty_selector": ".ldxx_con.last_ldxx",
    "detail_link_selector": "a[href*='/ldxxlm/']",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "网站地图",
        "include_selectors": [".ldxx_right", ".ldxx_con.last_ldxx"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "current_page_menu",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href*='/ldxxlm/']",
        "detail_name_selector": ".ldxx_con.last_ldxx",
        "detail_duty_selector": ".ldxx_con.last_ldxx",
        "detail_content_selector": ".ldxx_con.last_ldxx",
        "max_detail_links": 50,
    },
    "risk_flag": "规则入口兼作首位领导详情页；职务必须保留简介区完整现任原文，禁止删除机构前缀，领导分工和活动新闻不得混入",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldxx_right",
            "name_selector": "a[href*='/ldxxlm/']",
            "duty_selector": ".ldxx_con.last_ldxx",
            "detail_link_selector": "a[href*='/ldxxlm/']",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "领导分工",
                "include_selectors": [".ldxx_con.last_ldxx"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物目录和详情简介强字段直接提供姓名、现任职务及详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    """清理姓名中的网页排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_html(url: str) -> tuple[str, str]:
    """在线获取人物详情页HTML及最终地址。"""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _iter_leader_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """从当前领导目录按DOM顺序提取去重后的详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href*='/ldxxlm/']"):
        name = _clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name)
            or not re.search(r"/ldxxlm/\d{6}/t\d+_\d+\.html", href)
            or name in seen
        ):
            continue
        seen.add(name)
        links.append((name, urljoin(base_url, href)))
    return links


def _extract_current_duty(name: str, html: str) -> str:
    """仅在当前人物简介强字段中提取完整“现任……”原文。"""
    soup = BeautifulSoup(html, "html.parser")
    intro_node = soup.select_one(".ldxx_con.last_ldxx")
    intro = _clean_text(intro_node.get_text(" ", strip=True)) if intro_node else ""
    match = re.search(rf"{re.escape(name)}，(?P<duty>现任[^。]*。?)$", intro)
    return _clean_text(match.group("duty")) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前人物目录顺序抓取详情简介并保留完整现任原文。"""
    entry_url = str(page_rule.get("url", final_url))
    base_url = final_url or entry_url
    rows: list[dict[str, str]] = []

    for name, candidate_url in _iter_leader_links(html, base_url):
        if candidate_url.rstrip("/") == base_url.rstrip("/"):
            detail_html, resolved_url = html, base_url
        else:
            detail_html, resolved_url = _fetch_html(candidate_url)
        duty = _extract_current_duty(name, detail_html)
        duty = re.sub(r"^现任\s*", "", duty)
        if not duty:
            continue

        detail_url = "" if resolved_url.rstrip("/") == entry_url.rstrip("/") else resolved_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_ghhzrzy_leader_details_v1",
                "selector_summary": "领导目录详情链接；详情.ldxx_con.last_ldxx内姓名后的完整现任原文",
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
