from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PAGE_RULE = {"rule_id": "2428", "page_type": "列表转人物详情页", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "页面内置parse_page", "leader_region_selector": ".introduce_list", "item_selector": ".introduce_list a[href]", "risk_note": "详情.art_con首段为职务，后续为职责。", "confidence": "high"}

def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()

def compact_name(value: str) -> str:
    """清除姓名字间空白。"""
    return re.sub(r"\s+", "", clean_text(value))

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目录顺序在线读取详情首个职务段。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(page_rule["item_selector"]):
        name = compact_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        result = fetch_html_with_strategy(urljoin(final_url, link.get("href", "").strip()), "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        title = detail_soup.select_one(".wip_art h1, .htitle")
        if not title or compact_name(title.get_text(" ", strip=True)) != name:
            continue
        evidence = next((clean_text(p.get_text(" ", strip=True)) for p in detail_soup.select(".art_con p") if clean_text(p.get_text(" ", strip=True))), "")
        if evidence:
            rows.append({"name": name, "duty": "", "evidence": evidence, "detail_url": result.final_url})
    return rows

def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
