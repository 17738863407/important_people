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
    "rule_id": "4336",
    "page_type": "领导栏目转专题详情页",
    "structure_group": "cas_leadership_articles_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_cas_leadership_v1",
    "leader_region_selector": ".pageList, .list",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口同时含理事名单；仅进入会长副会长及党委秘书处两个当前领导专题。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "bounded_article_titles",
}


def parse_article(html: str, detail_url: str) -> list[dict]:
    """从专题正文中提取“协会职务+姓名”标题行。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select("p"):
        text = " ".join(paragraph.get_text(" ", strip=True).replace("\u3000", " ").split())
        matched = re.fullmatch(r"(中国资产评估协会[^，。]{1,40}?)\s+([\u3400-\u9fff·]{2,6})", text)
        if matched:
            duty = re.sub(r"\s+", "", matched.group(1))
            rows.append({"name": matched.group(2), "duty": duty, "detail_url": ""})
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口专题顺序抓取当前领导，并合并同一人物的多项网页职务。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select("a[href]"):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if "会长、副会长" in title or "党委、秘书处班子成员" in title:
            url = urljoin(final_url, str(anchor.get("href") or ""))
            if url not in links:
                links.append(url)
    if len(links) != 2:
        raise RuntimeError(f"当前领导专题链接数量异常：{len(links)}")

    merged: dict[str, dict] = {}
    for detail_url in links:
        result = fetch_by_raw_requests(detail_url)
        for row in parse_article(result.html, detail_url):
            name = row["name"]
            if name not in merged:
                merged[name] = row
            elif row["duty"] not in merged[name]["duty"].split("；"):
                merged[name]["duty"] += "；" + row["duty"]
    if not merged:
        raise RuntimeError("两个当前领导专题均未解析到‘协会职务+姓名’标题行")
    return list(merged.values())


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
