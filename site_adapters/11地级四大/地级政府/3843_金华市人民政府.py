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


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析市政府领导侧栏中一一对应的姓名、职务与详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for item in soup.select(".cr-submenu-inline .cr-menu-item"):
        anchor = item.select_one("a[href]")
        fields = item.select("em")
        if not anchor or len(fields) < 2:
            continue
        name = clean_text(fields[0].get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": duty,
                "detail_url": urljoin(source, str(anchor.get("href") or "")),
                "confidence": "high",
                "parser": "page_inline_jinhua_government_menu_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3843",
    "page_type": "领导详情侧栏",
    "load_mode": "静态HTML直出",
    "extract_mode": "list",
    "parser": "page_inline_jinhua_government_menu_v1",
    "leader_region_selector": ".cr-submenu-inline",
    "name_selector": ".cr-menu-item em:first-of-type",
    "duty_selector": ".cr-menu-item em:nth-of-type(2)",
    "detail_link_selector": ".cr-menu-item a[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "",
    "confidence": "high",
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
