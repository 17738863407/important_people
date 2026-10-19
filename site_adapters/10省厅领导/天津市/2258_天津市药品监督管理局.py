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
    "rule_id": "2258",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_drug_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_drug_directory_details_v1",
    "leader_region_selector": "div.zfxxgk.main",
    "name_selector": "目录人物文章a；详情.part_con .name",
    "duty_selector": ".part_con .info",
    "detail_link_selector": "目录内LDXX149668人物文章a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "机构信息",
        "include_selectors": ["div.zfxxgk.main"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": "目录内LDXX149668人物文章a[href]",
        "detail_name_selector": ".part_con .name",
        "detail_duty_selector": ".part_con .info",
        "detail_content_selector": ".part_con",
        "max_detail_links": 50,
    },
    "risk_flag": "目录区含面包屑和栏目链接；仅接受urljoin后属于LDXX149668的文章路径，详情姓名必须与目录一致",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.zfxxgk.main",
            "name_selector": "目录人物文章a；详情.part_con .name",
            "duty_selector": ".part_con .info",
            "detail_link_selector": "目录内LDXX149668人物文章a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "机构信息",
                "include_selectors": ["div.zfxxgk.main", ".part_con"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML目录提供人物链接，详情.part_con直接提供姓名和职务强字段"},
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _parse_detail(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".part_con .name")
    duty_node = soup.select_one(".part_con .info")
    name = _clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
    evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
    duty = re.sub(r"^职务[:：]\s*", "", evidence).strip()
    return name, duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序在线解析人物详情强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.zfxxgk.main a[href]"):
        expected_name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(base_url, str(link.get("href", "")))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", expected_name)
            or not re.search(r"/LDXX149668/\d{6}/t\d+_\d+\.html", detail_url)
            or expected_name in seen
        ):
            continue
        detail_html, resolved_url = _fetch_detail(detail_url)
        name, duty, evidence = _parse_detail(detail_html)
        if name != expected_name or not duty:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": resolved_url,
            "evidence": duty,
            "parser": "custom_tianjin_drug_directory_details_v1",
            "selector_summary": "目录LDXX149668文章；详情.part_con .name/.info强字段",
        })
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
