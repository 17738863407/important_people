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
    "rule_id": "3198",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_emergency_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_emergency_directory_details_v1",
    "leader_region_selector": "li.page_t",
    "name_selector": "li.page_t span.fl a[href]",
    "duty_selector": "详情页p.leaderIntro中姓名之前的原始职务",
    "detail_link_selector": "li.page_t span.fl a[href]",
    "content_scope": {
        "start_anchor": "领导班子成员",
        "end_anchor": "网站链接",
        "include_selectors": ["li.page_t", "p.leaderIntro"],
        "exclude_selectors": [".fr", "主管工作"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": "li.page_t span.fl a[href]",
        "detail_name_selector": "p.leaderIntro末尾姓名",
        "detail_duty_selector": "p.leaderIntro中姓名之前的文本",
        "detail_content_selector": "p.leaderIntro",
        "max_detail_links": 50,
    },
    "risk_flag": "入口页仅提供姓名目录；详情页职务与姓名在同一节点，须按入口姓名核对并只保留姓名前原文，排除主管工作",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "li.page_t",
            "name_selector": "span.fl a[href]",
            "duty_selector": "详情页p.leaderIntro",
            "detail_link_selector": "span.fl a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "主管工作",
                "include_selectors": ["p.leaderIntro"],
                "exclude_selectors": ["主管工作", "分管", "负责"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录及详情节点可稳定提供姓名、原始职务与人物链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_detail(html: str, expected_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("p.leaderIntro")
    if node is None:
        return "", ""
    text = _clean_text(node.get_text(" ", strip=True))
    compact_text = re.sub(r"\s+", "", text)
    if not compact_text.endswith(expected_name):
        return "", ""
    duty_compact = compact_text[: -len(expected_name)]
    if not duty_compact:
        return "", ""
    duty = text[: text.rfind(expected_name)].strip() if expected_name in text else duty_compact
    return expected_name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口目录DOM顺序，在线读取人物详情页中的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("li.page_t span.fl a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        requested_url = urljoin(base_url, str(link.get("href", "")))
        detail_html, detail_url = _fetch_detail(requested_url)
        detail_name, duty = _extract_detail(detail_html, name)
        if detail_name != name or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_emergency_directory_details_v1",
                "selector_summary": "li.page_t目录；详情p.leaderIntro姓名前原始职务",
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
