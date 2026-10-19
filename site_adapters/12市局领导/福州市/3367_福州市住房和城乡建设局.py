from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3367",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": "div.leader_name_list.leader_name_list_01",
    "person_selector": "li",
    "name_selector": "span",
    "duty_selector": "p",
    "detail_link_selector": "a[href]",
    "risk_flag": "机构职能页含其他链接，必须限定在唯一领导卡片区域内",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的全角及普通排版空格，不做语义补全。"""
    return re.sub(r"[\s\u3000]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导卡片DOM顺序提取姓名、原始职务和人物详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导卡片区域")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for person in region.select(page_rule["person_selector"]):
        name_node = person.select_one(page_rule["name_selector"])
        duty_node = person.select_one(page_rule["duty_selector"])
        link_node = person.select_one(page_rule["detail_link_selector"])
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        if name in seen_names:
            continue

        href = clean_text(link_node.get("href") if link_node else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": "page_inline_fuzhou_housing_leader_cards_v1",
                "selector_summary": (
                    "region=div.leader_name_list.leader_name_list_01；"
                    "person=li；name=span；duty=p；detail=a[href]"
                ),
            }
        )

    if not rows:
        raise RuntimeError("领导卡片区域未提取到有效人物")
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
