from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3908",
    "page_type": "多机构标签页领导卡片",
    "structure_group": "yulin_four_body_leader_tabs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "scoped_cards",
    "collector": "raw_http",
    "parser": "page_inline_yulin_government_tab_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader-tab-content > .tab-item",
    "name_selector": "a.leader-item .name",
    "duty_selector": "a.leader-item .post",
    "detail_link_selector": "a.leader-item[href]",
    "risk_flag": "页面静态包含市委、人大常委会、市政府、市政协四套同构卡片；须锁定含市政府秘书长字段的政府标签页",
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
    """锁定市政府标签页并按卡片原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = next(
        (
            node
            for node in soup.select(page_rule["leader_region_selector"])
            if any("市政府秘书长" == clean_text(post.get_text(" ", strip=True)) for post in node.select(".post"))
        ),
        None,
    )
    if region is None:
        raise RuntimeError("未定位到市政府领导标签页")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select("a.leader-item[href]"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".post")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = clean_text(card.get("href"))
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
                "selector_summary": "含市政府秘书长的.tab-item内leader-item姓名、职务和链接",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导标签页未提取到有效人物")
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
