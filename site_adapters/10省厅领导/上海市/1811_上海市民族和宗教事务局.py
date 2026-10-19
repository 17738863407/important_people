from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1811",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".acailer",
    "item_selector": ".acailer > p:has(img)",
    "risk_note": "正文按人物图片、姓名、职务、简介、分工重复排列，需以图片锚点限定人物边界。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def next_nonempty_paragraphs(paragraph, limit: int) -> list[str]:
    """从当前图片段之后依次取得同级非空段落文本。"""
    values: list[str] = []
    for sibling in paragraph.find_next_siblings("p"):
        if sibling.select_one("img"):
            break
        text = clean_text(sibling.get_text(" ", strip=True))
        if not text:
            continue
        values.append(text)
        if len(values) >= limit:
            break
    return values


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物图片版面顺序读取其后姓名和职务两个独立段落。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    rows: list[dict] = []
    for image_paragraph in region.find_all("p", recursive=False):
        if image_paragraph.select_one("img") is None:
            continue
        fields = next_nonempty_paragraphs(image_paragraph, 2)
        if len(fields) < 2:
            continue
        name = fields[0].replace(" ", "")
        evidence = fields[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": "",
            }
        )

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
