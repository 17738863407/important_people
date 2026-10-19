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
    "rule_id": "4348",
    "page_type": "Vue栏目转领导专题详情",
    "structure_group": "cwto_category_leader_articles_v1",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_cwto_leader_articles_v1",
    "leader_region_selector": "#app",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "栏目还含历史会长新闻；仅跟随标题精确为研究会会长、研究会副会长的当前专题。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "category_links_to_article_content",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从当前领导专题入口动态取得会长、副会长及秘书长。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    article_links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        title_node = anchor.find("span")
        title = " ".join((title_node or anchor).get_text(" ", strip=True).split())
        if title in {"研究会会长", "研究会副会长"}:
            article_links.append(urljoin(final_url, anchor["href"]))
    if len(article_links) != 2:
        raise RuntimeError(f"当前领导专题链接数量异常：{len(article_links)}")

    rows: list[dict] = []
    for article_url in article_links:
        result = fetch_html_with_strategy(
            article_url,
            strategy="extract",
            force_browser=True,
            timeout=30,
        )
        article = BeautifulSoup(result.html, "html.parser").select_one(".article-content")
        if article is None:
            raise RuntimeError(f"领导专题缺少正文区域：{article_url}")
        article_rows: list[dict] = []
        for paragraph in article.select("p"):
            text = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
            match = re.fullmatch(
                r"(会长|副会长兼秘书长|副会长)[：:]([\u3400-\u9fff·]{2,6})",
                text,
            )
            if match:
                duty, name = match.groups()
                article_rows.append({"name": name, "duty": duty, "detail_url": ""})
        if not article_rows:
            raise RuntimeError(f"领导专题存在，但未解析到职务姓名段落：{article_url}")
        if len(article_rows) == 1:
            article_rows[0]["detail_url"] = result.final_url
        rows.extend(article_rows)
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
