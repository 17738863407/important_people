from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0751",
    "page_type": "人物列表完整页",
    "structure_group": "机构概况动态栏目与领导字段卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div.div_item",
    "name_selector": "div.div_item",
    "duty_selector": "div.div_item",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.div_item"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "规则入口为机构概况，须从当前HTML动态发现办公厅领导栏目；同页锚点不得作为人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def field_value(item: BeautifulSoup, label: str) -> str:
    text = clean_text(item.get_text(" ", strip=True))
    match = re.search(rf"{label}\s*[:：]\s*(?P<value>.*?)(?=\s+(?:姓名|民族|职位)\s*[:：]|$)", text)
    return clean_text(match.group("value")) if match else ""


def find_leader_listing_url(html: str, final_url: str) -> str:
    """从规则入口当前HTML发现办公厅领导栏目，不保存第二入口业务网址。"""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href") or "")
        if text == "市政府办公厅领导":
            return urljoin(final_url, href).split("#", 1)[0]
    raise ValueError("规则入口未发现市政府办公厅领导栏目链接")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导栏目当前DOM顺序提取姓名和职位字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    listing_url = find_leader_listing_url(html, final_url)
    listing = fetch_html_with_strategy(listing_url, "raw_http")
    soup = BeautifulSoup(listing.html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("div.div_item"):
        name = field_value(item, "姓名")
        duty = field_value(item, "职位")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "机构概况动态栏目链接及领导页div.div_item姓名、职位字段",
            }
        )
        seen.add(name)
    if not rows:
        raise ValueError("办公厅领导栏目未发现可验证的人物记录")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
