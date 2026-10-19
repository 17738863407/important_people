from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1711",
    "domain": "mw.nmg.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "category_data_url_mixed_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "dynamic_subpage_list",
    "collector": "raw_http",
    "parser": "page_inline_category_data_url_mixed_leader_cards_v1",
    "category_link_selector": "a[data-url]",
    "category_text_anchor": "机关简介",
    "leader_region_selector": ".leaderList",
    "main_link_selector": "ul.leader1 a[href]",
    "other_link_selector": "ul.leader2 li a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "规则入口不直出人物；官方子页首人字段为主图链接后的同级p，其余人物字段位于leader2链接内p",
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
    """按入口目录文本锚点动态发现官方机关简介子页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    anchor = str(page_rule.get("category_text_anchor", ""))
    selector = str(page_rule.get("category_link_selector", ""))
    for link in soup.select(selector):
        if clean_text(link.get_text(" ", strip=True)) != anchor:
            continue
        data_url = str(link.get("data-url", "")).strip()
        if data_url:
            return urljoin(final_url, data_url)
    return ""


def append_record(
    records: list[dict[str, str]],
    seen: set[str],
    name: str,
    duty: str,
    detail_url: str,
    source_url: str,
    page_rule: dict[str, object],
) -> None:
    """校验并追加单个人物卡片记录。"""
    name = clean_name(name)
    duty = clean_text(duty)
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
        return
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
                "strategy=custom_parse_page；category=机关简介 a[data-url]；"
                "region=.leaderList；main=leader1 link+sibling p；other=leader2 link p"
            ),
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """发现官方机关简介子页，并按人物版面顺序解析混合卡片结构。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    source_url = str(page_rule.get("url", "")) or final_url
    content_url = discover_content_url(html, final_url or source_url, page_rule)
    if not content_url:
        return []

    result = fetch_by_raw_requests(content_url, timeout=40)
    soup = BeautifulSoup(result.html, "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    main_link = region.select_one(str(page_rule.get("main_link_selector", "")))
    direct_paragraphs = [
        clean_text(node.get_text(" ", strip=True)) for node in region.find_all("p", recursive=False)
    ]
    if main_link is not None and len(direct_paragraphs) >= 2:
        append_record(
            records,
            seen,
            direct_paragraphs[1],
            direct_paragraphs[0],
            urljoin(result.final_url or content_url, str(main_link.get("href", ""))),
            source_url,
            page_rule,
        )

    for link in region.select(str(page_rule.get("other_link_selector", ""))):
        paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in link.select("p")]
        if len(paragraphs) < 2:
            continue
        append_record(
            records,
            seen,
            paragraphs[1],
            paragraphs[0],
            urljoin(result.final_url or content_url, str(link.get("href", ""))),
            source_url,
            page_rule,
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
