from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3899",
    "page_type": "领导详情卡片列表",
    "structure_group": "xuchang_government_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "strong_cards",
    "collector": "requests",
    "parser": "page_inline_xuchang_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ewb-leader-items",
    "name_selector": ".ewb-leader-name",
    "duty_selector": ".ewb-leader-work",
    "detail_link_selector": ".ewb-leader-more[href]",
    "risk_flag": "页面另有一套仅含姓名的树形导航；须以完整领导卡片内成对姓名、职务和详情链接为准",
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
    """按完整领导卡片DOM顺序提取姓名、职务与详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到完整领导卡片列表")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select(".ewb-leader-item"):
        name_node = card.select_one(".ewb-leader-name")
        duty_node = card.select_one(".ewb-leader-work")
        link = card.select_one(".ewb-leader-more[href]")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = clean_text(link.get("href")) if link else ""
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
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
                "selector_summary": ".ewb-leader-item卡片姓名、职务及详细简历链接",
            }
        )

    if not rows:
        raise RuntimeError("完整领导卡片列表未提取到有效人物")
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
