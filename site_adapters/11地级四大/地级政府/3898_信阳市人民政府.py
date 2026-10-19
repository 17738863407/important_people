from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3898",
    "page_type": "政府门户领导分组卡片",
    "structure_group": "xinyang_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "grouped_links",
    "collector": "requests",
    "parser": "page_inline_xinyang_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ld_box",
    "name_selector": ".ld_list .ldimg_list a[href] p",
    "duty_selector": ".ld_list > .ld_l",
    "detail_link_selector": ".ld_list .ldimg_list a[href]",
    "risk_flag": "入口同时含政府文件、会议、发布会和公报；须限定.ld_box市政府领导卡片区",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导职务分组和人物卡片原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    title = region.select_one(":scope > .title") if region else None
    if region is None or "市政府领导" not in clean_text(title.get_text(" ", strip=True) if title else ""):
        raise RuntimeError("未找到市政府领导卡片区域")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > .ld_list"):
        duty_node = group.select_one(":scope > .ld_l")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty.endswith("长"):
            continue
        for link in group.select(".ldimg_list a[href]"):
            name_node = link.find("p")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": ".ld_box直属职务组及.ldimg_list人物链接",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导卡片区域未提取到有效人物")
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
