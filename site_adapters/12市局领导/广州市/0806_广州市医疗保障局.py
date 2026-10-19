from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0806",
    "page_type": "人物表格页",
    "structure_group": "图片相邻人物简介现任句",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物简介与分工段落相邻，必须仅取简介内完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序提取人物简介中的姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in article.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        profile_match = re.match(r"^([\u4e00-\u9fff]{2,4})，", text)
        current_match = re.search(r"现任([^。]*)。", text)
        if profile_match is None or current_match is None:
            continue
        name = profile_match.group(1)
        evidence = clean_text(current_match.group(1))
        if name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": ".article-content人物简介段落内完整现任句",
            }
        )
        seen.add(name)

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
