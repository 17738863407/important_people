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
    "rule_id": "1287", "page_type": "人物列表完整页", "structure_group": "shenyang_iit_labeled_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_iit_labeled_cards_v2",
    "leader_region_selector": "ul.xxgk_rul > li中含.x-leader-info的卡片",
    "name_selector": ".x-leader-info li的姓名标签对应font", "duty_selector": ".x-leader-info li的职务标签对应font",
    "detail_link_selector": ".x-leader-photo a[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "卡片还含介绍和办公室电话；只读取姓名、职务独立标签行",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def extract_labeled_value(card: BeautifulSoup, label: str) -> str:
    """读取指定标签行中的font原始字段。"""
    matches: list[str] = []
    for item in card.select(".x-leader-info li"):
        label_node = item.select_one("span")
        if label_node is None or label not in clean_text(label_node.get_text(" ", strip=True)):
            continue
        value_node = item.select_one("font")
        matches.append(clean_text(value_node.get_text(" ", strip=True) if value_node else ""))
    if len(matches) != 1 or not matches[0]:
        raise RuntimeError(f"人物卡片{label}字段命中异常")
    return matches[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片DOM顺序提取标签化姓名、原始职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = [card for card in soup.select("ul.xxgk_rul > li") if card.select_one(".x-leader-info")]
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        name = re.sub(r"\s+", "", extract_labeled_value(card, "姓名"))
        evidence = extract_labeled_value(card, "职务")
        detail_link = card.select_one(".x-leader-photo a[href]")
        href = clean_text(detail_link.get("href", "") if detail_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物卡片姓名或职务字段异常")
        if not detail_url or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到人物卡片")
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
