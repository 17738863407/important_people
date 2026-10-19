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
    "rule_id": "2728",
    "domain": "tjj.hubei.gov.cn",
    "page_type": "职务分组名单页",
    "structure_group": "hubei_statistics_duty_colon_name_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hubei_statistics_duty_colon_name_cards_v1",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片同时含分工说明，只将h4中的原始职务作为依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def resolve_detail_url(item: Tag, final_url: str) -> str:
    """从当前卡片中取得同站独立人物详情页。"""
    links = item.select("a[href]")
    link = next((node for node in links if clean_text(node.get_text(" ", strip=True)) == "详情"), None)
    if link is None:
        link = item.select_one(".pic a[href]")
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
    """按领导卡片顺序解析“职务：姓名”强结构。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".leader ul.list-b > li"):
        heading = item.select_one("h4")
        if not isinstance(heading, Tag):
            continue
        text = clean_text(heading.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        parts = re.split(r"[:：]", text)
        name = clean_text(parts[-1])
        duty = clean_text("：".join(parts[:-1]))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
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
                "selector_summary": "strategy=custom_parse_page；selector=.leader ul.list-b > li h4；format=duty:name",
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
