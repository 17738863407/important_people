from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3913",
    "page_type": "分组人物卡片",
    "structure_group": "changzhi_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_changzhi_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".provincial-leaders-inner",
    "name_selector": "li dl dd a",
    "duty_selector": "li > .provincial-leaders-position",
    "detail_link_selector": "li dl dd a[href]",
    "risk_flag": "页面含大量政府部门和检索文本；仅解析独立领导卡片容器",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按职务分组及卡片DOM顺序提取人物。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one(".provincial-leaders-inner")
    if region is None:
        raise RuntimeError("未定位到市政府领导卡片容器")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > li"):
        duty_node = group.select_one(":scope > .provincial-leaders-position")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for card in group.select(":scope > dl"):
            name_cell = card.find("dd", recursive=False)
            link = name_cell.find("a", href=True) if name_cell else None
            name = clean_name(link.get_text(" ", strip=True) if link else "")
            href = clean_text(link.get("href")) if link else ""
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
                    "selector_summary": ".provincial-leaders-inner直属li职务组及dl卡片",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导卡片容器未提取到有效人物")
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
