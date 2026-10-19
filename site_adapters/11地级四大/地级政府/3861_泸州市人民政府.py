from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def add_row(rows: list[dict[str, str]], name: str, duty: str, href: str, source: str) -> None:
    name = clean_text(name).replace(" ", ""); duty = clean_text(duty)
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
        rows.append({"name": name, "duty": "", "evidence": duty,
                     "detail_url": urljoin(source, href), "confidence": "high",
                     "parser": "page_inline_luzhou_government_cards_v1"})


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析市长主卡及副市长、秘书长卡片组。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", "")); rows: list[dict[str, str]] = []
    mayor = soup.select_one(".leaderBox .mayor h3.title")
    mayor_name = mayor.select_one("a.tit[href]") if mayor else None
    mayor_duty = mayor.select_one(".job") if mayor else None
    if mayor_name and mayor_duty:
        add_row(rows, mayor_name.get_text(" ", strip=True), mayor_duty.get_text(" ", strip=True),
                str(mayor_name.get("href") or ""), source)
    for group in soup.select(".leaderBox .boxA"):
        duty_node = group.select_one(":scope > .hd h3")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        for anchor in group.select(".leaderPicList li .con h3.title > a[href]"):
            add_row(rows, anchor.get_text(" ", strip=True), duty, str(anchor.get("href") or ""), source)
    return rows


PAGE_RULE = {"rule_id": "3861", "page_type": "市长主卡加领导分组卡片", "load_mode": "静态HTML直出",
             "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "grouped_list",
             "parser": "page_inline_luzhou_government_cards_v1", "leader_region_selector": ".leaderBox",
             "name_selector": ".mayor a.tit, .leaderPicList h3.title a", "duty_selector": ".mayor .job, .boxA > .hd h3",
             "detail_link_selector": ".mayor a.tit[href], .leaderPicList h3.title a[href]",
             "locator_strategy": "custom_parse_page", "risk_flag": "", "confidence": "high"}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
