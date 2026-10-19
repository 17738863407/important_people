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
    "rule_id": "0847",
    "domain": "gzw.sc.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "sichuan_sasac_wld_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_sasac_wld_list_v2",
    "leader_region_selector": ".wld .ld_list li",
    "name_selector": "strong",
    "duty_selector": "span",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "全页导航和新闻链接较多；只解析.wld .ld_list li内的委领导卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页列表中的连续空白。"""
    return " ".join(str(value or "").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按委领导卡片顺序提取姓名、原始职务和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        name_node = item.select_one(str(page_rule["name_selector"]))
        duty_node = item.select_one(str(page_rule["duty_selector"]))
        link = item.select_one(str(page_rule["detail_link_selector"]))
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue

        href = str(link.get("href") or "").strip() if link else ""
        detail_url = urljoin(source_url, href) if href else ""
        if detail_url in {source_url, str(page_rule["url"])}:
            detail_url = ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": ".wld .ld_list li内strong姓名、span职务和a[href]",
            }
        )

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
