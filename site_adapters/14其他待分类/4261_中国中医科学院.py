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
    "rule_id": "4261",
    "page_type": "现任领导卡片",
    "structure_group": "中国中医科学院现任领导卡片列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cacms_current_leaders_v1",
    "leader_region_selector": ".item a[href*='/current_leadership/detail/']",
    "name_selector": ".n1",
    "duty_selector": ".n2",
    "detail_link_selector": "a[href*='/current_leadership/detail/']",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "同页列有多个下属单位和机构目录，必须限定现任领导详情链接路径。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导卡片顺序读取姓名、职务和真实详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".item > a[href*='/current_leadership/detail/']"):
        name_node = link.select_one(".n1")
        duty_node = link.select_one(".n2")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link["href"]),
                "parser": page_rule["parser"],
                "selector_summary": "现任领导卡片 /current_leadership/detail/ 链接",
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
