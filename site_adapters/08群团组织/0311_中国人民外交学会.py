from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0311",
    "page_type": "人物列表完整页",
    "structure_group": "外交学会现任领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_cpifa_tfocus_pic_v2",
    "leader_region_selector": "ul#tFocus-pic",
    "name_selector": "li > h5.preh5",
    "duty_selector": "li div.picart strong",
    "detail_link_selector": "",
    "risk_flag": "卡片含性别和简介正文，仅取明确姓名与职务节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按卡片DOM顺序解析外交学会现任领导。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("ul#tFocus-pic > li"):
        name_node = card.select_one("h5.preh5")
        duty_node = card.select_one("div.picart strong")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_cpifa_tfocus_pic_v2",
                "selector_summary": (
                    "strategy=custom_parse_page；leader=ul#tFocus-pic>li；"
                    "name=h5.preh5；duty=div.picart strong"
                ),
            }
        )
    if not rows:
        raise RuntimeError("外交学会现任领导卡片未抽取到人物")
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
