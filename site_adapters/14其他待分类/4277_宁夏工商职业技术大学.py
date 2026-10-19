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
    "rule_id": "4277",
    "page_type": "现任领导卡片列表",
    "structure_group": "宁夏工商职业技术大学现任领导双字段列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_nxgs_leaders_v1",
    "leader_region_selector": ".xrld",
    "name_selector": ".xrld .ld",
    "duty_selector": ".xrld .ldzw",
    "detail_link_selector": ".xrld a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "现任领导区与页脚书记、校长邮箱并存，必须限定在 .xrld 列表。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导列表顺序提取姓名、职务和真实详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for card in soup.select(".xrld > ul > li"):
        link = card.select_one("a[href]")
        name_node = card.select_one(".ld")
        duty_node = card.select_one(".ldzw")
        if not link or not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "现任领导姓名、职务字段"})
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
