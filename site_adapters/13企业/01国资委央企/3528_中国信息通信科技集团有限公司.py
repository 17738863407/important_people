from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3528",
    "page_type": "人物列表完整页",
    "structure_group": "cict_group_leader_slider",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_cict_group_leader_slider_v2",
    "leader_region_selector": "div.abo04 div.swiper-wrapper",
    "name_selector": "div.text > b",
    "duty_selector": "div.text > p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "当前官网HTML直接包含8张集团领导卡片；只解析div.abo04轮播中的姓名和职务，不扫描页面其他人物文字",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析集团领导轮播中每张卡片可见层的姓名和原始职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select("div.abo04 div.swiper-wrapper div.swiper-slide li"):
        name_node = card.select_one("div.text > b")
        duty_node = card.select_one("div.text > p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_cict_group_leader_slider_v2",
            }
        )
    if not rows:
        raise RuntimeError("集团领导轮播未解析出有效人物卡片")
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
