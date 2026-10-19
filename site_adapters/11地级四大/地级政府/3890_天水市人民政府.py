from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3890",
    "page_type": "多机构领导分组卡片",
    "structure_group": "tianshui_cross_body_leader_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "scoped_grouped_cards",
    "collector": "requests",
    "parser": "page_inline_tianshui_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader",
    "name_selector": ".item .picBox li a[href]",
    "duty_selector": ".item > h2, .item01 .txt p",
    "detail_link_selector": ".item .picBox li a[href]",
    "risk_flag": "同一领导区并列市委、市政府、人大和政协职务组，且部分人物跨组重复；必须仅取市政府职务组并按首次出现去重",
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
    """仅从市长、常务副市长、副市长和市政府秘书长组抽取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导之窗分组区域")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    allowed_group_titles = {"市政府领导", "常务副市长", "副市长", "市政府秘书长"}
    for group in region.select(":scope > .item"):
        heading = group.find("h2", recursive=False)
        group_title = clean_text(heading.get_text(" ", strip=True) if heading else "")
        if group_title not in allowed_group_titles:
            continue
        for link in group.select(".picBox li a[href]"):
            if group_title == "市政府领导":
                name_node = link.select_one(".txt h4")
                duty_node = link.select_one(".txt p")
                name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
                duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            else:
                name_node = link.find("p")
                name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
                duty = group_title
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if not duty or name in seen_names:
                continue
            if urlparse(detail_url).scheme not in {"http", "https"}:
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
                    "selector_summary": ".leader直属市政府职务组及.picBox人物卡片",
                }
            )

    if not rows:
        raise RuntimeError("市政府职务组未提取到有效人物")
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
