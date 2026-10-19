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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按政府领导卡片DOM顺序提取当前现职人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for card in region.select("ul[id^='index-data-'] > li > a[href]"):
        spans = card.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        duty = clean_text(spans[0].get_text(" ", strip=True))
        name = clean_text(spans[1].get_text(" ", strip=True)).replace(" ", "")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(source_url, str(card.get("href") or ""))
        rows.append({"name": name, "duty": "", "evidence": duty, "detail_url": detail_url,
                     "confidence": "high", "parser": "page_inline_guangan_government_cards_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3824", "page_type": "图片人物卡片页", "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_guangan_government_cards_v1", "leader_region_selector": ".leader",
    "name_selector": "li a > span:nth-of-type(2)", "duty_selector": "li a > span:first-of-type",
    "detail_link_selector": "li a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "HTTP直连403，需Playwright渲染", "confidence": "high",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
