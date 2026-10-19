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
    "rule_id": "0932",
    "page_type": "汇总文章人物列表页",
    "structure_group": "taiyuan_ecology_leader_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_ecology_leader_list_v2",
    "leader_region_selector": "ul.List_list",
    "name_selector": "汇总文章#Zoom段落内a[href][title] strong",
    "duty_selector": "同段删除开头姓名后的完整可见文本",
    "detail_link_selector": "汇总文章段落内包含strong姓名的a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_summary_article"},
    "risk_flag": "入口仅提供领导信息汇总文章，人物须按汇总文章#Zoom段落顺序解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并人物链接title中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导列表DOM顺序解析姓名、职务和真实独立详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    lists = soup.select("ul.List_list")
    if len(lists) != 1:
        raise RuntimeError(f"领导列表数量异常：{len(lists)}")
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})\s+(?P<evidence>.+)$")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in lists[0].select(":scope > li"):
        node = item.select_one(":scope > a[href][title]")
        if node is None:
            continue
        title = clean_text(str(node.get("title", "")))
        if title == "领导信息":
            article_url = urljoin(final_url or page_rule["url"], str(node.get("href", "")))
            article = fetch_html_with_strategy(article_url, "raw_http")
            article_soup = BeautifulSoup(article.html or "", "html.parser")
            person_links = article_soup.select("#Zoom a[href][title]:has(strong)")
            for person_link in person_links:
                strong = person_link.select_one("strong")
                paragraph = person_link.find_parent("p")
                if strong is None or paragraph is None:
                    continue
                raw_name = clean_text(strong.get_text(" ", strip=True))
                name = re.sub(r"\s+", "", raw_name)
                if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
                    continue
                paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
                spaced_name = r"\s*".join(re.escape(character) for character in name)
                evidence = re.sub(rf"^\s*{spaced_name}\s*", "", paragraph_text, count=1)
                detail_url = urljoin(article.final_url, str(person_link.get("href", "")))
                if name in seen_names or not evidence or detail_url == article.final_url:
                    raise RuntimeError(f"汇总文章人物姓名、职务或详情链接异常：{name}")
                seen_names.add(name)
                records.append(
                    PersonRecord(
                        organization=page_rule["organization"],
                        url=page_rule["url"],
                        name=name,
                        duty=evidence,
                        detail_url=detail_url,
                        evidence=evidence,
                        confidence="high",
                        parser=page_rule["parser"],
                    )
                )
            continue
        match = pattern.fullmatch(title)
        if match is None:
            raise RuntimeError(f"人物链接title结构异常：{title}")
        name = match.group("name")
        evidence = clean_text(match.group("evidence"))
        detail_url = urljoin(final_url or page_rule["url"], str(node.get("href", "")))
        if name in seen_names or not evidence or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物姓名、职务或详情链接异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导列表没有可验证人物链接")
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
