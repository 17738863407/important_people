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
    "rule_id": "4278", "page_type": "现任领导卡片列表", "structure_group": "宁夏财经职业技术学院领导顶部卡片", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_nxcy_leaders_v1", "leader_region_selector": ".sc-lead .lead-top", "name_selector": ".sc-lead .lead-top .lead-name", "duty_selector": ".sc-lead .lead-top .lead-bt", "detail_link_selector": ".sc-lead .lead-top a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "隐藏详情区会重复人物，按当前顶部列表取一次并保留其详情链接。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见领导顶部列表顺序提取字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".sc-lead .lead-top > ul > li"):
        link = card.select_one(".lead-name a[href]")
        name_node = card.select_one(".lead-name")
        duty_node = card.select_one(".lead-bt")
        if not link or not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "可见领导顶部卡片"})
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
