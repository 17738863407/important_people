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
    """从领导卡片中提取姓名、页面原始职务及真实详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ggs-common-leader")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for card in region.select(".ggs-leader-right > li > a[href]"):
        name_node = card.select_one("h3")
        duty_node = card.select_one("p#ldjj-wrap")
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "") if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": urljoin(source_url, str(card.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_guigang_government_cards_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3825", "page_type": "图片人物卡片页", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_guigang_government_cards_v1", "leader_region_selector": ".ggs-common-leader",
    "name_selector": ".ggs-leader-right h3", "duty_selector": ".ggs-leader-right p#ldjj-wrap",
    "detail_link_selector": ".ggs-leader-right > li > a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "", "confidence": "high",
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
