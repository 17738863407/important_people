from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2665",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_finance_leader_window_title_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_finance_leader_window_title_links_v1",
    "leader_region_selector": ".zfxxgk_subtit文本为领导之窗的下一个zfxxgk_subcon",
    "name_selector": ".zfxxgk_subcon li a[title]标题开头姓名",
    "duty_selector": ".zfxxgk_subcon li a[title]标题中姓名后原始职务",
    "detail_link_selector": ".zfxxgk_subcon li a[href][title]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
        "detail_link_selector": ".zfxxgk_subcon li a[href][title]",
        "max_detail_links": 20,
    },
    "risk_flag": "leader_window_and_organization_sections_share_classes_and_first_visible_link_is_truncated",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "group_heading_selector": ".zfxxgk_subtit",
            "leader_list_selector": ".zfxxgk_subcon li a[href][title]",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线页面领导之窗分组直接提供完整title姓名职务及真实详情链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def find_leader_list(soup: BeautifulSoup):
    """以领导之窗标题为边界，避免混入同类机构设置列表。"""
    for heading in soup.select(".zfxxgk_subtit"):
        if normalize_space(heading.get_text(" ", strip=True)) != "领导之窗":
            continue
        return heading.find_next_sibling("div", class_="zfxxgk_subcon")
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导之窗列表顺序，从完整title动态提取姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_list = find_leader_list(soup)
    if leader_list is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in leader_list.select("li a[href][title]"):
        evidence = normalize_space(str(link.get("title", "")))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+)",
            evidence,
        )
        if not match:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        duty = re.sub(r"[（(]挂职[）)]", "", duty).rstrip("，、；; ")
        if name in seen_names or not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导之窗标题后紧邻列表；按DOM顺序从链接完整title拆分姓名和原始职务",
            }
        )
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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
