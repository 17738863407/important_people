from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2543",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#jgld",
    "item_selector": ".jgld:not(#jgld) > ul > li",
    "name_selector": ".jgld_content_1_2 b:first-of-type",
    "risk_note": "详情展开块与目录链接分处同页，须按姓名动态映射真实详情链接。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩字段排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按详情展开块顺序提取独立姓名、职务并映射目录链接。"""
    soup = BeautifulSoup(html, "html.parser")
    detail_urls = {
        clean_text(link.get("title", "")).replace(" ", ""): urljoin(
            final_url,
            link.get("href", "").strip(),
        )
        for link in soup.select("#jgld a.saleDeal[href][title]")
    }
    rows: list[dict] = []

    for item in soup.select(page_rule["item_selector"]):
        fields = item.select(".jgld_content_1_2 b")
        if len(fields) < 2:
            continue
        name = clean_text(fields[0].get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        detail_url = detail_urls.get(name, "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or not detail_url:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": detail_url,
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
