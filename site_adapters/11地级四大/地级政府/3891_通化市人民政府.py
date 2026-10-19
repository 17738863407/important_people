from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3891",
    "page_type": "领导分组卡片",
    "structure_group": "tonghua_government_leader_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "scoped_grouped_cards",
    "collector": "requests",
    "parser": "page_inline_tonghua_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ldzc_left",
    "name_selector": ".ldzc_left_ld .ldtp p a[href]",
    "duty_selector": ".ldzc_left_ld > span:first-of-type",
    "detail_link_selector": ".ldzc_left_ld .ldtp p a[href]",
    "risk_flag": "领导区域首组为副省长、市委书记；须保留该首组及市长、副市长、秘书长职务组",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_compact(value: object) -> str:
    """删除姓名或职务标题内部的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按市政府职务组与人物卡片原始顺序抽取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导之窗人物区域")

    base_url = final_url or page_rule["url"]
    allowed_duties = {"副省长、市委书记", "市长", "副市长", "秘书长"}
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > .ldzc_left_ld"):
        heading = group.find("span", recursive=False)
        duty = clean_compact(heading.get_text(" ", strip=True) if heading else "")
        if duty not in allowed_duties:
            continue
        for card in group.select(":scope > .ldtp"):
            link = card.select_one("p a[href]")
            if link is None:
                continue
            name = clean_compact(link.get_text(" ", strip=True))
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
                    "selector_summary": ".ldzc_left直属市政府职务组及.ldtp姓名链接",
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
