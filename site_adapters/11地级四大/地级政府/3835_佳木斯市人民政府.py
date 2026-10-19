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
    """限定市政府标签页，排除市委、人大和政协重复人名。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    section = next((node for node in soup.select(".section.js-tab") if node.get_text(" ", strip=True).startswith("市政府领导")), None)
    region = section.select_one("ul.szf li.ld-list") if section else None
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for link in region.select("p > a[href]"):
        duty_node, name_node = link.select_one("span"), link.select_one("i")
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "") if name_node else ""
        if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            rows.append({"name": name, "duty": "", "evidence": duty,
                         "detail_url": urljoin(source_url, str(link.get("href") or "")),
                         "confidence": "high", "parser": "page_inline_jiamusi_government_tab_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3835", "page_type": "同页多机构标签页", "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_jiamusi_government_tab_v1", "leader_region_selector": ".section.js-tab ul.szf li.ld-list",
    "name_selector": "p > a i", "duty_selector": "p > a span", "detail_link_selector": "p > a[href]",
    "locator_strategy": "custom_parse_page", "risk_flag": "HTTP直连403，且同页含多机构移动/桌面结构", "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
