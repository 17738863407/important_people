from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析两个正式人物分组，并按首次出现顺序合并同人的分组职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for group in soup.select("div.DnnModule-12876, div.DnnModule-6924"):
        group_node = group.select_one("div.second-content-title span.Head")
        if group_node is None:
            continue
        group_name = re.sub(r"\s+", "", group_node.get_text(" ", strip=True))
        for card in group.select("ul.gltd-ul > li.gltd-li"):
            title_node = card.select_one("a.news-title")
            if title_node is None:
                continue
            text = re.sub(r"\s+", " ", title_node.get_text(" ", strip=True)).strip()
            match = re.match(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·\s]{2,8})$", text)
            if match is None:
                continue
            name = re.sub(r"\s+", "", match.group("name"))
            duty = match.group("duty").strip()
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            grouped_evidence = f"{group_name}：{duty}"
            if name in row_by_name:
                row_by_name[name]["evidence"] += f"；{grouped_evidence}"
                row_by_name[name]["duty"] += f"；{grouped_evidence}"
                continue
            row = {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": grouped_evidence,
                "evidence": grouped_evidence,
                "confidence": "high",
                "parser": "page_grinm_management_groups_v1",
                "detail_url": "",
            }
            row_by_name[name] = row
            rows.append(row)
    return rows


PAGE_RULE = {
    "rule_id": "3497",
    "page_type": "职务分组名单页",
    "structure_group": "grinm_board_and_group_leaders",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "requests",
    "parser": "page_grinm_management_groups_v1",
    "leader_region_selector": "div.DnnModule-12876, div.DnnModule-6924",
    "name_selector": "a.news-title",
    "duty_selector": "a.news-title",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页含董事会和集团领导两个正式管理团队分组；卡片链接当前均返回模板配置提示，不能作为详情页",
    "confidence": "high",
}

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
