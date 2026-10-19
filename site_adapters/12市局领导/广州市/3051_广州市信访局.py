from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3051", "page_type": "人物表格页", "structure_group": "正文姓名括号职务分工段落",
    "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content", "name_selector": "p", "duty_selector": "p",
    "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".article-content"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文每段以姓名和全角括号职务开头，括号后职责必须排除", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def normalize_space(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取开头的姓名及括号内原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,4})（(?P<duty>[^（）]+)）")
    for paragraph in article.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if match is None or match.group("name") in seen:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "selector_summary": ".article-content段落开头姓名及全角括号职务"})
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
