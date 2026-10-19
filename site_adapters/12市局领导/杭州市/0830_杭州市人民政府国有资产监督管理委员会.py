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
    "rule_id": "0830",
    "page_type": "人物列表完整页",
    "structure_group": "hangzhou_sasac_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_sasac_leader_cards_v1",
    "leader_region_selector": ".bmld-switch .item",
    "name_selector": ".tit",
    "duty_selector": ".zw p",
    "detail_link_selector": "a.lbtn1[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "限定领导班子视窗，排除分工、电话及写信链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def valid_detail_url(href: str, final_url: str) -> str:
    """仅保留当前人物卡片的站内详情页。"""
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc or detail_url.rstrip("/") == final_url.rstrip("/"):
        return ""
    if "/art/" not in detail.path or not detail.path.endswith(".html"):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面DOM顺序解析国资委领导班子卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for item in soup.select(".bmld-switch .item"):
        name_node = item.select_one(".tit")
        duty_node = item.select_one(".zw p")
        detail_link = item.select_one("a.lbtn1[href]")
        name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": valid_detail_url(detail_link.get("href", ""), final_url) if detail_link else "",
                "selector_summary": ".bmld-switch .item内.tit姓名、.zw p职务、a.lbtn1详情",
            }
        )
    if not records:
        raise ValueError("未在国资委领导班子视窗中解析到有效人物")
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
