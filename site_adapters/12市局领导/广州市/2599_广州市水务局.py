from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2599",
    "page_type": "人物列表完整页",
    "structure_group": "渲染列表人物链接与详情现任句",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_detail",
    "collector": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#postList",
    "name_selector": "a.document-number",
    "duty_selector": ".article-content",
    "detail_link_selector": "a.document-number[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#postList"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "person_name_link", "max_detail_links": 50},
    "risk_flag": "入口人物列表依赖渲染，详情页须限于人物简介中的完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_space(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面配置动态发现公开目录接口，再按接口顺序抓取人物详情。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    entry_url = str(page_rule.get("url") or final_url)
    entry = fetch_html_with_strategy(entry_url, strategy="raw_http", timeout=60)
    sid_match = re.search(r"\bSID:\s*['\"](?P<sid>\d+)['\"]", entry.html)
    classify_id = urlparse(entry_url).fragment.strip()
    if sid_match is None or not classify_id.isdigit():
        raise RuntimeError("入口页未发现公开目录SID或领导分类编号")
    parsed_entry = urlparse(entry.final_url)
    api_url = (
        f"{parsed_entry.scheme}://{parsed_entry.netloc}/gkmlpt/api/all/"
        f"{classify_id}?page=1&sid={sid_match.group('sid')}"
    )
    api_result = fetch_html_with_strategy(api_url, strategy="raw_http", timeout=60)
    payload = json.loads(api_result.html)
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise RuntimeError("领导分类接口缺少articles数组")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for article_item in articles:
        if not isinstance(article_item, dict):
            continue
        name = normalize_space(article_item.get("title", "")).replace(" ", "")
        detail_url = urljoin(entry.final_url, str(article_item.get("url") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        detail = fetch_html_with_strategy(detail_url, strategy="raw_http", timeout=60)
        article = BeautifulSoup(detail.html, "html.parser").select_one(".article-content")
        if article is None:
            continue
        detail_text = normalize_space(article.get_text(" ", strip=True))
        intro_match = re.search(r"简介\s*[：:].*?(现任\s*[^。]*。)", detail_text)
        if intro_match is None:
            continue
        evidence = normalize_space(intro_match.group(1)).removeprefix("现任").strip().removesuffix("。")
        rows.append({
            "name": name,
            "duty": evidence.removeprefix("现任").strip().removesuffix("。"),
            "evidence": evidence,
            "detail_url": detail.final_url,
            "selector_summary": "#postList人物链接及详情.article-content简介现任句",
        })
        seen.add(name)
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
