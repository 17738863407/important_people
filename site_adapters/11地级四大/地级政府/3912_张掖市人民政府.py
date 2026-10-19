from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3912",
    "page_type": "党委政府并列人物卡片",
    "structure_group": "zhangye_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zhangye_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ldzcItem（标题为市政府领导）",
    "name_selector": ".ldnm, .ldzclist .nm",
    "duty_selector": ".ldzw, .tabnav1",
    "detail_link_selector": ".ldzp a[href], .ldzclist a[href]",
    "risk_flag": "市委与市政府两套同构区域并列；必须以区域标题锁定市政府",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def build_row(name: str, duty: str, href: str, base_url: str, page_rule: dict) -> dict | None:
    """校验强结构字段并构造一条人物记录。"""
    detail_url = urljoin(base_url, href) if href else ""
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
        return None
    if urlparse(detail_url).scheme not in {"http", "https"}:
        return None
    return {
        "name": name,
        "duty": duty,
        "evidence": duty,
        "detail_url": detail_url,
        "confidence": "high",
        "parser": page_rule["parser"],
        "selector_summary": "标题为市政府领导的.ldzcItem直属职务组",
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """锁定市政府区域，按主卡及页面职务分组顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = next(
        (
            item
            for item in soup.select(".ldzcItem")
            if clean_text((item.select_one(":scope > .swld") or {}).get_text(" ", strip=True))
            == "市政府领导"
        ),
        None,
    )
    if region is None:
        raise RuntimeError("未定位到市政府领导区域")

    rows: list[dict] = []
    seen_names: set[str] = set()
    lead_card = region.select_one(":scope > .ldzp")
    if lead_card is not None:
        name_node = lead_card.select_one(".ldnm")
        duty_node = lead_card.select_one(".ldzw")
        link = lead_card.select_one("a[href]")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        row = build_row(name, duty, clean_text(link.get("href")) if link else "", base_url, page_rule)
        if row is not None:
            seen_names.add(name)
            rows.append(row)

    for tab in region.select(":scope > .tabnav1"):
        duty = clean_text(tab.get_text(" ", strip=True))
        group = tab.find_next_sibling("div", class_="ldzr")
        if group is None or not duty:
            continue
        for link in group.select("ul.ldzclist li a[href]"):
            name_node = link.select_one(".nm")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            if name in seen_names:
                continue
            row = build_row(name, duty, clean_text(link.get("href")), base_url, page_rule)
            if row is None:
                continue
            seen_names.add(name)
            rows.append(row)

    if not rows:
        raise RuntimeError("市政府领导区域未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
