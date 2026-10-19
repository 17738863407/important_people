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


def add_row(rows: list[dict[str, str]], name: str, duty: str, href: str, source: str) -> None:
    name = clean_text(name).replace(" ", "")
    duty = clean_text(duty)
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and duty:
        rows.append({"name": name, "duty": "", "evidence": duty,
                     "detail_url": urljoin(source, href), "confidence": "high",
                     "parser": "page_inline_linzhi_government_groups_v1"})


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析市长详情摘要及其后常务副市长、副市长、秘书长分组。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    mayor = soup.select_one(".sz-details .fr > p")
    mayor_anchor = mayor.select_one("a[href]") if mayor else None
    if mayor and mayor_anchor:
        name = mayor_anchor.get_text(" ", strip=True)
        duty = clean_text(mayor.get_text(" ", strip=True)).removeprefix(clean_text(name)).strip()
        add_row(rows, name, duty, str(mayor_anchor.get("href") or ""), source)
    for title in soup.select(".center-main > .title:not(.sz)"):
        duty = clean_text(title.get_text(" ", strip=True))
        group = title.find_next_sibling("ul", class_="lists")
        for anchor in group.select(":scope > li > a[href]") if group else []:
            name_node = anchor.select_one("p")
            add_row(rows, name_node.get_text(" ", strip=True) if name_node else "", duty,
                    str(anchor.get("href") or ""), source)
    return rows


PAGE_RULE = {
    "rule_id": "3856", "page_type": "市长摘要加领导分组卡片", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "grouped_list",
    "parser": "page_inline_linzhi_government_groups_v1", "leader_region_selector": ".center-main",
    "name_selector": ".sz-details .fr p a, ul.lists li p", "duty_selector": ".sz-details .fr p, .title",
    "detail_link_selector": ".sz-details a[href], ul.lists li > a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "", "confidence": "high",
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
