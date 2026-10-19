from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1445",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".content",
    "row_selector": ".content .leader_xq",
    "name_selector": "h4",
    "duty_selector": "h4",
    "detail_link_selector": "a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "姓名与职务合并为“职务：姓名”h4；入口HTTP返回412，online链需浏览器兜底。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物块DOM顺序拆分h4中的职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".content .leader_xq"):
        heading = card.select_one("h4")
        link = card.select_one("a[href]")
        text = normalize_text(heading.get_text(" ", strip=True) if heading is not None else "")
        match = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·]{2,5})", text)
        if match is None:
            continue
        duty, name = (normalize_text(part) for part in match.groups())

        detail_url = ""
        if link is not None:
            href = normalize_text(link.get("href", ""))
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                detail_url = urljoin(final_url, href)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty})

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
