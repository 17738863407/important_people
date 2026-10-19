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
    "rule_id": "2743", "page_type": "人物目录详情页", "structure_group": "shenyang_statistics_group_article_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_statistics_group_article_v2",
    "leader_region_selector": "入口‘局领导及分工’链接对应文章.view", "name_selector": "人物标题p内办公电话括号之前末尾姓名",
    "duty_selector": "人物标题p内姓名之前原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "shared_group_article"},
    "risk_flag": "入口链接指向多人共用分工文章，不得作为个人详情链接；职责段不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """动态抓取多人分工文章并按标题段顺序解析人物。"""
    from crawler_core.fetcher import fetch_online_html
    from crawler_core.models import PersonRecord

    entry = BeautifulSoup(html or "", "html.parser")
    links = [
        link for link in entry.select("a[href]")
        if clean_text(link.get_text(" ", strip=True)) == "局领导及分工"
    ]
    if len(links) != 1:
        raise RuntimeError(f"入口的局领导及分工链接数量异常：{len(links)}")
    article_url = urljoin(final_url, str(links[0].get("href", "")).strip())
    article_html, article_final_url = fetch_online_html(article_url)
    article = BeautifulSoup(article_html or "", "html.parser")
    views = article.select(".view")
    if len(views) != 1:
        raise RuntimeError(f"分工文章正文数量异常：{len(views)}")
    records: list[object] = []
    seen_names: set[str] = set()
    title_pattern = re.compile(r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,10})\s*[（(]\s*办公电话")
    for paragraph in views[0].select("p"):
        title = clean_text(paragraph.get_text(" ", strip=True))
        match = title_pattern.match(title)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("duty"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物标题职务为空或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError(f"分工文章没有有效人物标题：{article_final_url}")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
