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
    "rule_id": "0934",
    "domain": "hbnysy.hubei.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hubei_agriculture_center_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hubei_agriculture_center_leader_cards_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导卡片的职务节点存在两种结构，按卡片内强结构字段依次读取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩节点文本中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def is_hidden(node: Tag) -> bool:
    """判断当前节点或其祖先是否被页面明确隐藏。"""
    for current in [node, *node.parents]:
        if not isinstance(current, Tag):
            continue
        style = re.sub(r"\s+", "", str(current.get("style", ""))).lower()
        classes = {str(item).lower() for item in current.get("class", [])}
        if (
            current.has_attr("hidden")
            or str(current.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide", "d-none"})
        ):
            return True
    return False


def resolve_detail_url(item: Tag, final_url: str) -> str:
    """从当前人物头像链接动态取得同站独立详情页。"""
    link = item.select_one(".pic > a[href]")
    if link is None:
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
    """按页面可见领导卡片顺序提取姓名、原始职务与详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".leader li"):
        if not isinstance(item, Tag) or is_hidden(item):
            continue
        name_node = item.select_one("h4 b")
        duty_node = item.select_one("h4 span") or item.select_one(".leader-info h5")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
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
                "selector_summary": "strategy=custom_parse_page；selector=.leader li > h4 b；duty=h4 span|.leader-info h5",
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
