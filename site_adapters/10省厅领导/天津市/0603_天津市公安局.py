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
    "rule_id": "0603",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_police_leader_redirect_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_police_leader_redirect_details_v1",
    "leader_region_selector": ".rightBox .commonList",
    "name_selector": "li.comItem .title",
    "duty_selector": ".leader-left .leader-intro p",
    "detail_link_selector": "li.comItem a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "网站地图",
        "include_selectors": [".rightBox .commonList"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "redirect_detail_pages",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".rightBox .commonList li.comItem a[href]",
        "detail_name_selector": ".leader-name",
        "detail_duty_selector": ".leader-left .leader-intro p",
        "detail_content_selector": ".leadercontaier",
        "max_detail_links": 50,
    },
    "risk_flag": "目录链接先进入站内中间页，须从当前响应动态解析target_url；详情简介和分工不得并入职务依据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".rightBox .commonList",
            "name_selector": "li.comItem .title",
            "duty_selector": ".leader-left .leader-intro p",
            "detail_link_selector": "li.comItem a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "网站地图",
                "include_selectors": [".rightBox .commonList"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录和详情强字段可复现，中间页target_url可从实时响应解析",
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


def _clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留全部具体兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", _clean_text(value)).strip()


def _fetch_detail(url: str) -> tuple[str, str]:
    """在线读取中间页，并跟随页面当前声明的target_url。"""
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding

    match = re.search(r"target_url\s*=\s*['\"](?P<url>[^'\"]+)['\"]", response.text)
    if match is None:
        return response.text, response.url

    target_url = urljoin(response.url, match.group("url"))
    detail = requests.get(target_url, headers=headers, timeout=30)
    detail.raise_for_status()
    detail.encoding = detail.apparent_encoding or detail.encoding
    return detail.text, detail.url


def _parse_detail(html: str) -> tuple[str, str]:
    """从人物详情页强字段读取姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".leader-name")
    duty_node = soup.select_one(".leader-left .leader-intro p")
    name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
    duty = _clean_duty_evidence(duty_node.get_text(" ", strip=True)) if duty_node else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序在线解析领导详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".rightBox .commonList li.comItem a[href]"):
        name_node = link.select_one(".title")
        expected_name = _clean_name(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
        intermediate_url = urljoin(base_url, str(link.get("href", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name) or expected_name in seen:
            continue

        detail_html, detail_url = _fetch_detail(intermediate_url)
        name, duty = _parse_detail(detail_html)
        if name != expected_name or not duty:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_police_leader_redirect_details_v1",
                "selector_summary": ".commonList目录；target_url跳转；详情.leader-name/.leader-intro p",
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
