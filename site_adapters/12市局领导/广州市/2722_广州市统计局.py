from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2722",
    "page_type": "人物列表完整页",
    "structure_group": "渲染列表人物链接与详情简介职务姓名连续文本",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_detail",
    "collector": "online",
    "parser": "builtin_parse_page",
    "leader_region_selector": "a.document-number",
    "name_selector": "a.document-number",
    "duty_selector": ".article-content p",
    "detail_link_selector": "a.document-number[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["a.document-number"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "person_name_link", "max_detail_links": 50},
    "risk_flag": "入口人物列表依赖渲染；详情简介以职务和姓名连续呈现",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按渲染列表顺序抓取详情，并解析简介段落中姓名之前的原始职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a.document-number[href]"):
        name = compact_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        detail = fetch_html_with_strategy(detail_url, "requests")
        article = BeautifulSoup(detail.html, "html.parser").select_one(".article-content")
        if article is None:
            continue
        duty = ""
        for paragraph in article.select("p"):
            paragraph_text = compact_text(paragraph.get_text(" ", strip=True))
            marker = f"{name}，"
            if marker not in paragraph_text:
                continue
            duty = paragraph_text.split(marker, 1)[0].strip("，,。；;")
            if duty:
                break
        if not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail.final_url,
            "selector_summary": "渲染列表人物链接及详情.article-content简介首段姓名前职务",
        })
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
