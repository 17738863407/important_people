from __future__ import annotations

import re
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
    "rule_id": "3936",
    "domain": "www.gdhyzx.gov.cn",
    "page_type": "分组人物目录",
    "structure_group": "heyuan_cppcc_sidebar_groups_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_heyuan_cppcc_sidebar_groups_v1",
    "leader_region_selector": ".sidebar .nav, .nav",
    "name_selector": ".nav-item-cnt .nav-item-title[href]",
    "duty_selector": ":scope > .nav-item-title",
    "detail_link_selector": ".nav-item-cnt .nav-item-title[href]",
    "content_scope": {"include_selectors": [".nav"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "右侧正文只展示当前选中领导，必须以左侧完整分组目录为准",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".nav",
            "group_selector": ":scope > .nav-cnt > .nav-item",
            "duty_selector": ":scope > .nav-item-title",
            "name_selector": ":scope > .nav-item-cnt > .nav-item > a.nav-item-title[href]",
        },
        "api": {"enabled": False, "reason": "静态HTML侧栏已完整列出职务分组、姓名和人物页链接"},
    },
}


def normalize_text(value: str) -> str:
    """清理导航字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧政协领导分组目录顺序提取全部现任领导。"""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one(".nav")
    nav_content = nav.find("div", class_="nav-cnt", recursive=False) if nav else None
    if nav_content is None:
        raise RuntimeError("未找到政协领导左侧分组目录 .nav > .nav-cnt")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in nav_content.find_all("div", class_="nav-item", recursive=False):
        duty_node = group.find("a", class_="nav-item-title", recursive=False)
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if duty not in {"主席", "副主席", "秘书长"}:
            continue
        group_content = group.find("div", class_="nav-item-cnt", recursive=False)
        if group_content is None:
            continue
        for item in group_content.find_all("div", class_="nav-item", recursive=False):
            link = item.find("a", class_="nav-item-title", href=True, recursive=False)
            name = normalize_text(link.get_text(" ", strip=True) if link else "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".nav>.nav-cnt直属职务组；组内nav-item-title姓名链接",
                }
            )
    if not rows:
        raise RuntimeError("政协领导分组目录未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
