from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4082",
    "page_type": "领导简介卡片页",
    "structure_group": "iae_leader_news_text_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_iae_leader_news_text_card",
    "leader_region_selector": ".news-txt",
    "risk_flag": "简介段落含分工，依据说明仅保存标题中的现任职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从领导简介标题的“职务 姓名”结构提取姓名、职务和独立详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".news-txt"):
        heading = card.select_one("h2")
        if heading is None:
            continue
        text = re.sub(r"\s+", "", heading.get_text(" ", strip=True))
        split = next(
            (
                (text[:-name_length], text[-name_length:])
                for name_length in (2, 3, 4)
                if len(text) > name_length and re.search(r"(?:所长|书记|主任|院长)$", text[:-name_length])
            ),
            None,
        )
        if split is None:
            continue
        link = heading.select_one("a[href]")
        rows.append({
            "name": split[1],
            "duty": split[0],
            "evidence": split[0],
            "detail_url": urljoin(final_url, link["href"]) if link else "",
        })
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
