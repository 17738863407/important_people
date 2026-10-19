from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3227",
    "page_type": "人物表格页",
    "structure_group": "sichuan_drug_leader_titles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_sichuan_drug_leader_titles_v1",
    "leader_region_selector": "#list_right dl.list_box_list",
    "name_selector": ".jg-list-title > strong",
    "duty_selector": ".jg-list-title > span",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导介绍",
        "end_anchor": "",
        "include_selectors": ["#list_right dl.list_box_list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "全页包含大量导航和单位链接；仅解析领导标题块的strong/span字段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#list_right dl.list_box_list",
            "name_selector": ".jg-list-title > strong",
            "duty_selector": ".jg-list-title > span",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导介绍",
                "end_anchor": "",
                "include_selectors": ["#list_right dl.list_box_list"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导标题块直接包含姓名和职务，无独立人物链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理不换行空格和排版空白，不改变职务语义。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导标题块中的姓名和职务，继承页面表格顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for title in soup.select("#list_right dl.list_box_list .jg-list-title"):
        name_node = title.find("strong", recursive=False)
        duty_node = title.find("span", recursive=False)
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_sichuan_drug_leader_titles_v1",
                "selector_summary": "#list_right .jg-list-title；strong姓名；span职务",
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
