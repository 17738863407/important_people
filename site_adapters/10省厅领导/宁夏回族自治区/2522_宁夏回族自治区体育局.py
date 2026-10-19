from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2522",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".view",
    "row_selector": ".view > p",
    "name_selector": "职务标题段末尾姓名",
    "duty_selector": "职务标题段开头党组职务",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "正文同时含人物照片、人口属性和分工；仅接受以党组职务开头、以合法姓名结尾的独立标题段。",
}


def normalize_text(text: str) -> str:
    """仅压缩段落中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文职务标题段顺序提取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".view")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    for paragraph in region.select(":scope > p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>党组[^。；]{0,40}?(?:局长|组组长))\s+(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,4})", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = normalize_text(match.group("duty"))
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty})

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
