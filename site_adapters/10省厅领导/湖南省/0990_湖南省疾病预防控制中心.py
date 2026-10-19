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
    "rule_id": "0990",
    "domain": "www.hncdc.com",
    "page_type": "人物列表完整页",
    "structure_group": "hncdc_leader_name_duty_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hncdc_leader_name_duty_links_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同路径还含面包屑和分页链接，仅解析同时具有姓名、职务子节点的人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名内部的排版空格。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def resolve_detail_url(link: Tag, final_url: str) -> str:
    """校验当前人物链接对应的同站独立详情页。"""
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
    """按领导信息人物链接顺序提取姓名、原始职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/lingdaoxinxi/"]:has(.link-value):has(.link-desc)'):
        name_node = link.select_one(".link-value")
        duty_node = link.select_one(".link-desc")
        if not isinstance(name_node, Tag) or not isinstance(duty_node, Tag):
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": resolve_detail_url(link, final_url),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；link=leadership a with .link-value + .link-desc；detail=current-href",
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
