from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2517",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_service_breadcrumb_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "entry_then_list_then_detail_http",
    "parser": "page_nanning_service_breadcrumb_list_detail_v2",
    "leader_region_selector": "权威详情页面包屑领导介绍目录",
    "name_selector": "目录人物链接文本",
    "duty_selector": "详情正文完整现任句",
    "detail_link_selector": "目录内/ldjs/t人物链接",
    "detail_strategy": {"required": True, "mode": "entry_to_list_to_detail", "max_detail_links": 30},
    "risk_flag": "权威入口为单个人物页；必须从当前页面包屑动态发现领导目录，再按目录顺序逐详情解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "面包屑领导介绍链接", "detail_link_selector": "目录内/ldjs/t人物链接", "detail_content_selector": "#UCAP-CONTENT"}, "api": {"enabled": False, "reason": "入口、目录与人物详情均由静态HTML提供"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_index_url(html: str, final_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        label = normalize_layout(anchor.get_text(" ", strip=True))
        url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if label == "领导介绍" and urlparse(url).path.rstrip("/").endswith("/ldjs"):
            return url
    return ""


def discover_people(html: str, index_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    people: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        name = normalize_layout(anchor.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(index_url, str(anchor.get("href", "")).strip())
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or "/ldjs/t" not in detail_url or name in seen:
            continue
        seen.add(name)
        people.append((name, detail_url))
    return people


def parse_detail(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT")
    if region is None:
        return ""
    text = normalize_layout(region.get_text(" ", strip=True))
    if expected_name not in text:
        return ""
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        return ""
    return re.sub(r"^现任\s*", "", match.group(0)).strip(" ，,。；;：: ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    index_url = discover_index_url(html, final_url)
    if not index_url:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    index_result = fetch_html_with_strategy(index_url, strategy="requests")
    people = discover_people(index_result.html, index_result.final_url)
    rows: list[dict[str, str]] = []
    for name, detail_url in people:
        evidence = parse_detail(fetch_html_with_strategy(detail_url, strategy="requests").html, name)
        if not evidence:
            raise RuntimeError(f"人物详情页缺少可回指的姓名或完整现任句：{detail_url}")
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "" if detail_url == final_url else detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "权威详情页动态发现领导目录；目录人物链接按DOM顺序逐详情提取完整现任句"})
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
