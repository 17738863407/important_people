from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "2786",
    "page_type": "图片人物块相邻简介",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#ivs_content",
    "item_selector": "#ivs_content img[alt]",
    "risk_note": "姓名取人物图片alt文件名，职务取图片后、下一图片前首个非空段落。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物图片顺序提取相邻首行中的姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for image in region.select("img[alt]"):
        name = clean_text(Path(image.get("alt", "")).stem)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        image_paragraph = image.find_parent("p")
        if image_paragraph is None:
            continue
        intro = ""
        for sibling in image_paragraph.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            if sibling.select_one("img[alt]") is not None:
                break
            text = clean_text(sibling.get_text(" ", strip=True))
            if text:
                intro = text
                break
        if not intro.endswith(name):
            continue
        evidence = intro[: -len(name)].strip("：:，, ")
        if not evidence:
            continue
        seen.add(name)
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
