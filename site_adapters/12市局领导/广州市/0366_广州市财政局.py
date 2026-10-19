from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0366",
    "page_type": "人物表格页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": ".article-content",
    "person_selector": "p",
    "risk_flag": "正文混有个人简介和工作分工，只接受纯姓名段后紧邻的广州市财政局职务段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除纯姓名段中的排版空白，不做语义补全。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文段落顺序提取纯姓名段及其紧邻的原始职务段。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导分工文章正文")

    texts = [
        text
        for node in region.select(page_rule["person_selector"])
        if (text := clean_text(node.get_text(" ", strip=True)))
    ]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for index, text in enumerate(texts[:-1]):
        name = clean_name(text)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            continue
        duty = clean_text(texts[index + 1])
        if not duty.startswith("广州市财政局"):
            continue
        if not re.search(r"党组|局长|巡视员|纪检监察|党委", duty):
            continue
        if name in seen_names:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_guangzhou_finance_adjacent_paragraphs_v2",
                "selector_summary": "region=.article-content；name=纯姓名p；duty=紧邻机构职务p；detail=none",
            }
        )

    if not rows:
        raise RuntimeError("文章正文未提取到有效姓名职务段")
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
