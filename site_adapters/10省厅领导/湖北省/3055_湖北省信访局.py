from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3055",
    "domain": "xfj.hubei.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "hubei_petition_leader_bio_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_hubei_petition_leader_bio_cards_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物简介含性别学历等信息，仅提取当前人物块中的完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def resolve_detail_url(item: Tag, final_url: str) -> str:
    """校验当前人物头像对应的同站独立详情页。"""
    link = item.select_one(".leader_img a[href]")
    if not isinstance(link, Tag):
        return ""
    href = clean_text(str(link.get("href", "")))
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    detail_url = urljoin(final_url, href)
    detail_parts = urlparse(detail_url)
    entry_parts = urlparse(final_url)
    if detail_parts.netloc.lower() != entry_parts.netloc.lower():
        return ""
    if detail_parts._replace(fragment="") == entry_parts._replace(fragment=""):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导人物块顺序提取姓名、完整现任句和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("ul.leaders > li"):
        heading = item.select_one(".leader_text h6")
        bio = item.select_one(".leader_text .view")
        if not isinstance(heading, Tag) or not isinstance(bio, Tag):
            continue
        heading_text = clean_text(heading.get_text(" ", strip=True))
        name = clean_text(re.split(r"[:：]", heading_text)[-1])
        bio_text = clean_text(bio.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", bio_text)
        evidence = clean_text(current_match.group(0) if current_match else "")
        duty = evidence.removeprefix("现任").rstrip("。").strip()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": resolve_detail_url(item, final_url),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；item=ul.leaders > li；name=h6-after-colon；duty=.leader_text .view current-sentence",
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
