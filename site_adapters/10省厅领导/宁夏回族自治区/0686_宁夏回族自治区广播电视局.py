from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0686",
    "domain": "gdj.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_index_latest_article_paragraph_groups_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_index_latest_article_paragraph_groups_v2",
    "content_selector": ".gk-artcle-con .view",
    "paragraph_selector": "p",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "栏目文章地址会更新；正文按姓名/个人信息/职务/分工连续分组，姓名后必须紧邻含性别与出生信息段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


ROLE_PATTERN = re.compile(r"(党组书记|局长|副局长|纪检监察组组长|总工程师|巡视员)")


def clean_text(value: object) -> str:
    """归一网页排版空白，不改变原始职务语义。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s+([，。、；：）])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从栏目动态进入最新领导简介，并按正文连续段落顺序提取。"""
    from urllib.parse import urljoin

    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("content_selector", "")))
    if region is None:
        article_link = next(
            (
                link
                for link in soup.select("a[href]")
                if clean_text(link.get_text(" ", strip=True)) == "自治区广播电视局领导简介"
                and str(link.get("href") or "").endswith(".html")
            ),
            None,
        )
        if article_link is None:
            raise RuntimeError("领导信息栏目未找到最新领导简介文章")
        article_url = urljoin(final_url or str(page_rule.get("url", "")), str(article_link.get("href") or ""))
        article = fetch_html_with_strategy(article_url, "raw_http")
        soup = BeautifulSoup(article.html or "", "html.parser")
        region = soup.select_one(str(page_rule.get("content_selector", "")))
    if region is None:
        raise RuntimeError("最新领导简介文章未找到正文区域")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in region.select("p")]
    paragraphs = [text for text in paragraphs if text]

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, name in enumerate(paragraphs):
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        if index + 1 >= len(paragraphs):
            continue
        profile = paragraphs[index + 1]
        if not re.search(r"(?:男|女)，", profile) or "出生" not in profile:
            continue
        duty = next(
            (candidate for candidate in paragraphs[index + 2 : index + 4] if ROLE_PATTERN.search(candidate)),
            "",
        )
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.gk-artcle-con .view；"
                    "name=独立姓名p且后接性别/出生信息p；duty=再后2个非空p内首个职务段；"
                    "exclude=个人信息+分工"
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
