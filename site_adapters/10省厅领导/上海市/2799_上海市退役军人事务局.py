from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2799",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#container",
    "item_selector": "#container div.introduce",
    "risk_note": "简介首句为机构职务，后续为个人信息和分工，必须截断在首个句号。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按人物介绍卡片顺序提取姓名、简介首句和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        link = item.select_one("div.name a[href]")
        intro = item.select_one("div.intro")
        if link is None or intro is None:
            continue
        name = clean_text(link.get_text(" ", strip=True))
        intro_text = clean_text(intro.get_text(" ", strip=True))
        first_sentence = intro_text.split("。", 1)[0]
        evidence = f"{first_sentence}。" if first_sentence else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, link.get("href", "").strip()),
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
