from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0063",
    "page_type": "列表转人物详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.introduce_list",
    "item_selector": "div.introduce_list div.zfxxgk_zdgkc a[href]",
    "risk_note": "详情首段以姓名、并列职务、职责开头；职务边界为职责动词前的逗号。",
    "confidence": "high",
}


def compact_text(value: str) -> str:
    """清除页面中的姓名字间空格和其他排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按入口姓名顺序在线读取详情首段中的原始职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        name = compact_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(final_url, link.get("href", "").strip())
        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        evidence = ""
        for paragraph in detail_soup.select("div.art_con p"):
            text = compact_text(paragraph.get_text(" ", strip=True))
            if not text.startswith(name):
                continue
            after_name = text[len(name) :].lstrip("：:，, ")
            evidence = re.split(r"[，,](?=主持|负责|办理)", after_name, maxsplit=1)[0]
            break
        if not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": result.final_url,
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
