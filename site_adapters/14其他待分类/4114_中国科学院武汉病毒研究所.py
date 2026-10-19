from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4114",
    "page_type": "leader_image_text_list",
    "structure_group": "S4114",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "fetch_mode": "online",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": "div.TRS_Editor > p",
    "risk_notes": "每张图片下方的同一段落直接给出“职务：姓名”，没有人物详情链接。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """仅解析领导图片条目内的职务—姓名文本。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff]{2,4})", text)
        if match is None:
            continue
        duty, name = match.group(1).strip(), match.group(2).strip()
        if duty and name:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
