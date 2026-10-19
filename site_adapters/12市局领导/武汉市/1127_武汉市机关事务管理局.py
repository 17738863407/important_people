from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1127",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_agency_affairs_grouped_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_agency_affairs_grouped_cards_v2",
    "leader_region_selector": ".article-box .lead_text",
    "name_selector": "li.list-item p.text_name",
    "duty_selector": ".title-box span.text",
    "detail_link_selector": "li.list-item > a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "li.list-item > a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "卡片职务在分组标题中，卡片内部另含分工文本，分工不得并入职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并分组与卡片文本空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按分组卡片DOM顺序提取姓名、分组职务和独立详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    groups = soup.select(".article-box .lead_text")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for group in groups:
        duty_nodes = group.select(":scope > .title-box span.text")
        items = group.select("li.list-item")
        if len(duty_nodes) != 1 or len(items) != 1:
            raise RuntimeError(f"领导分组职务或卡片数量异常：duty={len(duty_nodes)} item={len(items)}")
        evidence = clean_text(duty_nodes[0].get_text(" ", strip=True))
        item = items[0]
        name_node = item.select_one("p.text_name")
        link = item.select_one(":scope > a[href]")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        detail_url = urljoin(final_url, link.get("href", "").strip() if link else "")
        parts = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导卡片姓名或职务异常：{name} {evidence}")
        if link is None or parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"领导卡片详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"领导卡片姓名或链接重复：{name} {detail_url}")
        seen_names.add(name)
        seen_links.add(detail_url)
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
        raise RuntimeError("领导简介区域没有人物卡片")
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
