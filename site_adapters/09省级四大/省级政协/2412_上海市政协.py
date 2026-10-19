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
    "rule_id": "2412",
    "page_type": "职务分组人物卡片页",
    "structure_group": "shanghai_cppcc_grouped_leaders",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_shanghai_cppcc_grouped_leaders_v1",
    "leader_region_selector": "div.con20",
    "name_selector": "div.con20 a.blue14[title][href]",
    "duty_selector": "div.con20 a.blue14[title][href]",
    "detail_link_selector": "div.con20 a.blue14[title][href]",
    "detail_strategy": {"required": True, "mode": "group_card_profile"},
    "risk_flag": "同人可同时属于党组成员和主席会议成员，按首次出现顺序动态合并分组职务",
    "confidence": "high",
}


def _clean_text(text: str) -> str:
    return (
        text.replace("\u3000", " ")
        .replace("\u2002", " ")
        .replace("\u200d", "")
        .replace("\xa0", " ")
        .strip()
    )


def _compact_name(text: str) -> str:
    return "".join(_clean_text(text).split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析上海市政协领导页的两个领导分组。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}

    for section in soup.select("div.con20"):
        group_title_node = section.select_one(".ldtitle")
        group_title = _clean_text(group_title_node.get_text(" ", strip=True)) if group_title_node else ""
        if not group_title:
            continue
        for link in section.select("a.blue14[title][href]"):
            text = _clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
            parts = text.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            name = _compact_name(parts[0])
            duty = _clean_text(parts[1])
            if not name or not duty:
                continue
            evidence_part = f"{group_title}：{duty}"
            existing = row_by_name.get(name)
            if existing is not None:
                evidence_parts = existing["evidence"].split("；")
                if evidence_part not in evidence_parts:
                    evidence_parts.append(evidence_part)
                    existing["evidence"] = "；".join(evidence_parts)
                    existing["duty"] = existing["evidence"]
                continue
            detail_url = urljoin(final_url, str(link.get("href") or ""))
            if detail_url == str(page_rule.get("url") or "").strip():
                detail_url = ""
            row = {
                    "name": name,
                    "duty": evidence_part,
                    "detail_url": detail_url,
                    "evidence": evidence_part,
                    "confidence": "high",
                    "parser": "page_shanghai_cppcc_grouped_leaders_v1",
            }
            row_by_name[name] = row
            rows.append(row)

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
