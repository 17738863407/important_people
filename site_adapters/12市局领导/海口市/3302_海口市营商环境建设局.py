from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3302",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_business_environment_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "haikou_business_environment_leader_cards_v1",
    "leader_region_selector": "a.leaidx",
    "name_selector": "em",
    "duty_selector": "span",
    "detail_link_selector": "a.leaidx[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "保留页面原始分号，不补写机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def clean_duty(value: str) -> str:
    """仅清理排版空白与外层方括号，不改写原始标点或机构语义。"""
    return re.sub(r"\s+", "", value or "").strip(" []【】")


def valid_detail_url(href: str, final_url: str) -> str:
    """仅保留当前卡片指向的真实站内人物详情页。"""
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc or detail_url.rstrip("/") == final_url.rstrip("/"):
        return ""
    if not re.search(r"/ldxx/\d{6}/t\d+\.shtml(?:$|[?#])", detail_url):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面DOM顺序解析营商环境建设局领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for card in soup.select("a.leaidx"):
        name_node = card.select_one("em")
        duty_node = card.select_one("span")
        name = clean_name(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = clean_duty(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": valid_detail_url(card.get("href", ""), final_url),
                "selector_summary": "a.leaidx > em姓名 + span原始职务",
            }
        )
    if not records:
        raise ValueError("未在营商环境建设局领导卡片中解析到有效人物")
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
