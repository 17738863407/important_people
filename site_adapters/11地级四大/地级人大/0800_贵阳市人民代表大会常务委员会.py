from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0800",
    "page_type": "职务分组名单页",
    "structure_group": "gysrd_sidebar_duty_name_links_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".leftsidebar ul.other_ld",
    "name_selector": "li > a > label",
    "duty_selector": "li > a > span",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "inline_with_verified_links",
        "detail_link_selector": ".leftsidebar ul.other_ld > li > a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "入口为当前党组书记详情页；同页侧栏提供完整现任名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩姓名和职务节点中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split()).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏可见顺序提取职务、姓名和独立人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    basis_url = str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leftsidebar ul.other_ld > li > a[href]"):
        duty_node = link.select_one(":scope > span")
        name_node = link.select_one(":scope > label")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        if not duty or not name or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if detail_url.rstrip("/") == basis_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
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
