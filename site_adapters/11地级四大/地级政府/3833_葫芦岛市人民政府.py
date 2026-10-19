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
    """依次以职务标题与其后紧邻人物列表建立对应。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".column-col-1")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for heading in region.select(":scope > .column-name"):
        duty = clean_text(heading.get_text(" ", strip=True))
        people = heading.find_next_sibling("ul", class_=re.compile(r"^lingdaolist-txt(?:-nophoto)?$"))
        if not duty or people is None:
            continue
        for link in people.select("li > a[href]"):
            node = link.select_one(".lingdaoxm")
            name_source = node.get_text(" ", strip=True) if node else link.get_text(" ", strip=True)
            name = clean_text(name_source).replace(" ", "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source_url, str(link.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_huludao_government_groups_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3833", "page_type": "职务分组卡片页", "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_huludao_government_groups_v1", "leader_region_selector": ".column-col-1",
    "name_selector": ".lingdaoxm", "duty_selector": ".column-name h3",
    "detail_link_selector": ".lingdaolist-txt a[href]", "locator_strategy": "custom_parse_page",
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
