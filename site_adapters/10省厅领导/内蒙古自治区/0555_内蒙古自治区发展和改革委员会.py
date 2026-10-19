from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0555",
    "domain": "fgw.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "category_data_url_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "dynamic_subpage_list",
    "collector": "raw_http",
    "parser": "page_inline_category_data_url_leader_cards_v1",
    "category_query_parameter": "cid",
    "category_link_selector": "a[cid][data-url]",
    "leader_list_selector": ".leaderList li a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "规则入口不直出人物；须按URL中的cid定位目录data-url，再解析官方子页人物卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩卡片字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def discover_content_url(html: str, final_url: str, page_rule: dict[str, object]) -> str:
    """按业务入口URL中的cid动态发现官方内容子页。"""
    source_url = str(page_rule.get("url", "")) or final_url
    parameter = str(page_rule.get("category_query_parameter", "cid"))
    category_id = parse_qs(urlparse(source_url).query).get(parameter, [""])[0]
    if not category_id:
        return ""

    soup = BeautifulSoup(html or "", "html.parser")
    selector = str(page_rule.get("category_link_selector", ""))
    for link in soup.select(selector):
        if str(link.get("cid", "")).strip() != category_id:
            continue
        data_url = str(link.get("data-url", "")).strip()
        if data_url:
            return urljoin(final_url or source_url, data_url)
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """发现官方内容子页，并按人物卡片DOM顺序提取姓名、职务和详情链接。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    source_url = str(page_rule.get("url", "")) or final_url
    content_url = discover_content_url(html, final_url, page_rule)
    if not content_url:
        return []

    result = fetch_by_raw_requests(content_url, timeout=40)
    soup = BeautifulSoup(result.html, "html.parser")
    selector = str(page_rule.get("leader_list_selector", ""))
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(selector):
        paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in link.select("p")]
        if len(paragraphs) < 2:
            continue
        duty = paragraphs[0]
        name = clean_name(paragraphs[1])
        href = str(link.get("href", "")).strip()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        detail_url = urljoin(result.final_url or content_url, href) if href else ""
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；category=a[cid][data-url] matched from source cid；"
                    "list=.leaderList li a；duty=p[1]；name=p[2]"
                ),
            }
        )

    return records


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
