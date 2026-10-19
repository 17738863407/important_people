from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1962",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_finance_leadership_article_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_finance_leadership_article_v3",
    "leader_region_selector": ".trs_editor_view > p > strong",
    "name_selector": "领导分工文章加粗段落首个空白前",
    "duty_selector": "领导分工文章加粗段落姓名后的完整职务",
    "detail_link_selector": "a[href][title='领导分工']",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_shared_leadership_article",
        "detail_link_selector": "a[href][title='领导分工']",
        "max_detail_links": 1,
    },
    "risk_flag": "栏目已改为单篇领导分工汇总文章；只提取正文中独立加粗的姓名职务段落，排除其后的主持、分管和联系职责。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".trs_editor_view > p > strong",
            "detail_link_selector": "a[href][title='领导分工']",
            "detail_content_selector": "#UCAP-CONTENT .trs_editor_view",
        },
        "api": {"enabled": False, "reason": "领导列表和一对一人物详情均由静态HTML提供"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b\ufeff]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_leadership_article(html: str, final_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", "")).strip()
        label = normalize_layout(anchor.get_text(" ", strip=True))
        title = normalize_layout(str(anchor.get("title", "")))
        if label == "领导分工" or title == "领导分工":
            return urljoin(final_url, href)
    return ""


def parse_leadership_article(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select("#UCAP-CONTENT .trs_editor_view > p > strong")
    rows: list[tuple[str, str]] = []
    for node in nodes:
        raw = re.sub(r"[\s\u3000\u00a0\u2002-\u200b\ufeff]+", " ", node.get_text(" ", strip=True)).strip()
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,8})\s+(?P<duty>.+)", raw)
        if match is None:
            raise RuntimeError(f"领导姓名职务段落格式异常：{raw}")
        name = match.group("name")
        duty = normalize_layout(match.group("duty"))
        if not duty:
            raise RuntimeError(f"领导职务为空：{name}")
        rows.append((name, duty))
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    article_url = discover_leadership_article(html, final_url)
    if not article_url:
        raise RuntimeError("领导班子栏目未找到“领导分工”文章")
    from crawler_core.fetcher import fetch_html_with_strategy

    detail = fetch_html_with_strategy(article_url, strategy="raw_http")
    people = parse_leadership_article(detail.html)
    if not people:
        raise RuntimeError("领导分工文章未解析到姓名职务段落")
    rows: list[dict[str, str]] = []
    for name, evidence in people:
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导班子栏目动态发现领导分工文章；按正文加粗段落DOM顺序提取姓名和完整职务",
            }
        )
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
