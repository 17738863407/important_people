from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩页面字段中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导介绍目录顺序动态抓取人物详情页。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#part6 .pr > ul")
    if region is None:
        raise ValueError("未找到领导介绍人物列表 #part6 .pr > ul")

    source_url = str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in region.select(":scope > li"):
        link = item.select_one("a[href*='content_']")
        if link is None:
            continue
        list_name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[一-鿿·]{2,6}", list_name):
            continue
        detail_url = urljoin(final_url or source_url, str(link.get("href", "")))
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)

        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome")
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
            name_node = detail_soup.select_one("#part8 > ul.ul2 > h1")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
            if name != list_name:
                raise ValueError(f"目录姓名与详情页姓名不一致：{list_name} != {name}")

            evidence = ""
            for paragraph in detail_soup.select("#part8 .content p"):
                paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
                match = re.search(r"现任[^。]*。", paragraph_text)
                if match:
                    evidence = re.sub(r"^现任\s*", "", match.group(0)).rstrip("。")
                    break
            if not evidence:
                raise ValueError("详情页当前人物简介中未找到完整现任职务句")
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": source_url,
                    "name": name,
                    "duty": evidence,
                    "detail_url": detail_result.final_url or detail_url,
                    "evidence": evidence,
                    "confidence": "high",
                    "parser": "page_inline_chengdu_veterans_detail_profile_v1",
                }
            )
        except Exception as error:
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": source_url,
                    "name": list_name,
                    "duty": "",
                    "detail_url": detail_url,
                    "evidence": f"详情页抽取失败：{error}",
                    "confidence": "失败",
                    "parser": "page_inline_chengdu_veterans_detail_profile_v1",
                }
            )
    return rows


PAGE_RULE = {
    "rule_id": "2810",
    "page_type": "人物目录详情页",
    "structure_group": "chengdu_veterans_leader_profiles",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "chrome_cdp",
    "parser": "page_inline_chengdu_veterans_detail_profile_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "普通 HTTP 受防护；现任职务位于独立详情页简介段落",
    "confidence": "high",
}


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
