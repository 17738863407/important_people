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
    "rule_id": "3267",
    "page_type": "人物表格页",
    "structure_group": "ymg_leadership_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "builtin_parse_page",
    "leader_region_selector": "a[onclick='getContent(this)']及领导信息子页div#leader",
    "name_selector": "div#leader p:first-of-type",
    "duty_selector": "div#leader p:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口由目标为mainframe的栏目链接切换子页；人物卡片链接仅为当前页锚点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """只清理网页排版空白，不改写职务语义。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从入口动态解析领导信息子页，并按卡片顺序提取姓名和职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html, "html.parser")
    leadership_link = next(
        (
            link
            for link in entry_soup.select("a[href][target='mainframe']")
            if _clean_text(link.get_text(" ", strip=True)) == "领导信息"
        ),
        None,
    )
    if leadership_link is None:
        raise RuntimeError("入口页未找到目标为mainframe的领导信息链接")
    leadership_url = urljoin(final_url, str(leadership_link.get("href") or ""))
    result = fetch_html_with_strategy(leadership_url, "online", force_browser=True)
    soup = BeautifulSoup(result.html, "html.parser")

    records: list[PersonRecord] = []
    for card in soup.select("div#leader"):
        fields = card.select("a > p")
        if len(fields) < 2:
            continue
        name = _clean_text(fields[0].get_text(" ", strip=True))
        duty = _clean_text(fields[1].get_text(" ", strip=True))
        if not name or not duty:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="领导信息子页div#leader内前两个p",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
