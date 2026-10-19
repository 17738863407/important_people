from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3903",
    "page_type": "职务行人物行交替表格",
    "structure_group": "yantai_government_alternating_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "alternating_group_table",
    "collector": "requests",
    "parser": "page_inline_yantai_government_table_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "table.ldtb",
    "name_selector": "a.link14b[href]",
    "duty_selector": "直属行span职务标题",
    "detail_link_selector": "a.link14b[href]",
    "risk_flag": "页面下方紧接组成部门和政务栏目；领导表格内职务标题行与人物行交替且嵌套多层表格",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按直属表格行顺序继承最近职务标题并提取姓名链接。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政府领导表格")

    body = region.find("tbody", recursive=False)
    direct_rows = body.find_all("tr", recursive=False) if body else []
    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    pending_duty = ""
    for table_row in direct_rows:
        direct_span = table_row.find("span", recursive=False)
        if direct_span is None:
            first_cell = table_row.find("td", recursive=False)
            direct_span = first_cell.find("span", recursive=False) if first_cell else None
        heading = clean_text(direct_span.get_text(" ", strip=True) if direct_span else "")
        if heading.endswith("长"):
            pending_duty = heading
            continue
        if not pending_duty:
            continue
        for link in table_row.select("a.link14b[href]"):
            name = clean_name(link.get_text(" ", strip=True))
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": pending_duty,
                    "evidence": pending_duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": "table.ldtb直属职务行与下一直属人物行a.link14b",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导表格未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
