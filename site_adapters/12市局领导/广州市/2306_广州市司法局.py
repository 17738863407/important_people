from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2306",
    "page_type": "人物列表完整页",
    "structure_group": "渲染后人物链接与详情个人简介现任句",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_detail",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#postList a.document-number",
    "name_selector": "#postList a.document-number",
    "duty_selector": ".article-content",
    "detail_link_selector": "#postList a.document-number[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#postList", ".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "入口人物列表由接口渲染，须浏览器复核并逐详情提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白，并清理标点前空格。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def extract_current_sentence(html: str, name: str) -> str:
    """从人物详情页个人简介中提取完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    for content in soup.select(".article-content"):
        text = clean_text(content.get_text(" ", strip=True))
        if name not in text or "个人简介" not in text:
            continue
        match = re.search(r"现任[^。]*。", text)
        if match is not None:
            return re.sub(
                r"^现任(?:职务)?\s*[：:]?\s*",
                "",
                clean_text(match.group(0)),
            ).rstrip("。；; ")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按渲染后人物列表顺序抓取并解析详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_urls: set[str] = set()

    for anchor in soup.select("#postList a.document-number[href]"):
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(anchor.get("href") or ""))
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name)
            or name in seen
            or detail_url in seen_urls
        ):
            continue
        detail_result = fetch_html_with_strategy(detail_url, "online")
        evidence = extract_current_sentence(detail_result.html, name)
        if not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url,
                "selector_summary": "渲染后#postList人物链接及详情.article-content个人简介完整现任句",
            }
        )
        seen.add(name)
        seen_urls.add(detail_url)

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
