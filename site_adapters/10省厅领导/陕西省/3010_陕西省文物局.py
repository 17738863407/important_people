from __future__ import annotations

import sys
import re
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3010",
    "page_type": "政务公开入口转领导卡片页",
    "structure_group": "shaanxi_relics_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_article",
    "collector": "static_http",
    "parser": "page_inline_shaanxi_wwj_leader_card_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "政务公开入口的领导信息链接 > .wwldgl",
    "name_selector": ".wwldgl .glxx span",
    "duty_selector": ".wwldgl .glxx p:first-of-type",
    "detail_link_selector": ".wwldgl .glpic a[href]",
    "risk_flag": "规则主表为政务公开入口，须动态跟随当前领导信息栏目；第二个p为分工，不得并入职务",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析陕西省文物局领导信息子页。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    entrance = BeautifulSoup(html, "lxml")
    leader_link = next(
        (
            anchor
            for anchor in entrance.select("a[href]")
            if clean_text(anchor.get_text(" ", strip=True)) == "领导信息"
        ),
        None,
    )
    if leader_link is None:
        raise RuntimeError("政务公开入口未找到领导信息栏目链接")
    leader_url = urljoin(final_url, str(leader_link.get("href", "")))
    leader_result = fetch_by_raw_requests(leader_url, timeout=30)
    soup = BeautifulSoup(leader_result.html, "lxml")
    if not soup.select(".wwldgl"):
        raise RuntimeError("当前领导信息栏目未发现.wwldgl领导卡片")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in soup.select(".wwldgl"):
        info = block.select_one(".glxx")
        if not info:
            continue
        name_node = info.select_one("span")
        duty_node = info.select_one("p")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
            continue
        link = block.select_one("a[href]")
        detail_url = urljoin(leader_result.final_url, link.get("href", "")) if link else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_shaanxi_wwj_leader_card_v2",
            }
        )
    if not rows:
        raise RuntimeError("领导卡片未解析出有效姓名和职务")
    return rows


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
