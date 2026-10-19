from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1307",
    "page_type": "多人物详情合并页",
    "structure_group": "姓名职务标题与相邻人物简介现任句",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".content_article p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".content_article"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online会误随页面脚本跳至空关键词搜索页，需保留原始HTTP正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面顺序配对姓名职务标题和紧随其后的人物简介。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".content_article p")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, paragraph in enumerate(paragraphs):
        profile_text = clean_text(paragraph.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", profile_text)
        if current_match is None:
            continue

        title_text = ""
        for previous in reversed(paragraphs[:index]):
            candidate = clean_text(previous.get_text(" ", strip=True))
            if candidate:
                title_text = candidate
                break
        title_match = re.match(r"^([\u4e00-\u9fff·]{2,4})\s+.+$", title_text)
        if title_match is None:
            continue
        name = title_match.group(1)
        evidence = re.sub(r"^现任\s*", "", clean_text(current_match.group(0))).removesuffix("。").strip()
        if name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": ".content_article姓名职务标题及相邻简介内完整现任句",
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
