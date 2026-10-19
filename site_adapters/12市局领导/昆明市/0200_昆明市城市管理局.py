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
    "rule_id": "0200",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_duty_name_title_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_duty_name_title_list_v1",
    "leader_region_selector": "div.data-table-item",
    "name_selector": "p.w659 a[href]",
    "duty_selector": "p.w659 a[href]",
    "detail_link_selector": "p.w659 a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "max_detail_links": 50,
    },
    "risk_flag": "普通HTTP可能触发网站安全防护；人物标题格式为职务在前、姓名在后",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def split_duty_name(text: str) -> tuple[str, str]:
    line = clean_text(text)
    match = re.match(r"^(.+?)\s+([\u4e00-\u9fa5]{2,4})$", line)
    if not match:
        return "", ""
    duty = clean_text(match.group(1))
    name = clean_text(match.group(2))
    if not duty or not name:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面标题中的“职务 姓名”结构和原始DOM顺序提取人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one("p.w659 a[href]")
        if link is None:
            continue
        line = clean_text(link.get_text(" ", strip=True))
        name, duty = split_duty_name(line)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": page_rule["parser"],
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
