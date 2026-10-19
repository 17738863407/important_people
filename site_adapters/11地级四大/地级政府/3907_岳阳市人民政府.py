from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3907",
    "page_type": "政府门户领导分组卡片",
    "structure_group": "yueyang_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "grouped_links",
    "collector": "requests",
    "parser": "page_inline_yueyang_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".col-lg-7",
    "name_selector": ".leader-list li p a[href]",
    "duty_selector": ".leader-list > h3",
    "detail_link_selector": ".leader-list li p a[href]",
    "risk_flag": "首页同栏后接要闻、人事、会议等列表；须限定市政府领导左侧栏的leader-list职务组",
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
    regions = soup.select(page_rule["leader_region_selector"])
    region = next((node for node in regions if "市政府领导" in clean_text(node.get_text(" ", strip=True))), None)
    if region is None:
        raise RuntimeError("未找到市政府领导左侧栏")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > .leader-list"):
        heading = group.find("h3", recursive=False)
        duty = clean_text(heading.get_text(" ", strip=True) if heading else "")
        if not duty.endswith("长"):
            continue
        for link in group.select("li p a[href]"):
            name = clean_name(link.get_text(" ", strip=True))
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
                    "selector_summary": "市政府领导左侧栏.leader-list标题及人物姓名链接",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导职务组未提取到有效人物")
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
