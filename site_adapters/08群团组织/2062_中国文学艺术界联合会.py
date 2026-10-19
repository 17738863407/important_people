from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2062",
    "page_type": "职务分组名单页",
    "structure_group": "cflac_presidium_and_secretariat_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "grouped_name_cards",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": "div.leadmain > div.bg1 .row.row1, div.leadmain > div.bg2 > .row.row3, div.leadmain > div.bg3 > .row.pdt30, div.leadmain > div.bg3 > .row.pdt10",
    "name_selector": ".leadlist > li > .name > a",
    "duty_selector": ".row-title img[data-original]",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "主席团",
        "end_anchor": "书记处书记",
        "include_selectors": ["div.leadmain > div.bg1", "div.leadmain > div.bg2", "div.leadmain > div.bg3"],
        "exclude_selectors": ["div.bg4"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "同页四个现行分组需完整提取；书记处人员与副主席或主席团委员重叠，需合并明确职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_name(value: str) -> str:
    """确定性清理姓名卡中的排版空白。"""
    return re.sub(r"\s+", "", value.replace("\u3000", " ").replace("\xa0", " "))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析主席、副主席、主席团委员和书记处书记四个可见分组。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    group_specs = (
        ("div.leadmain > div.bg1 .row.row1", "主席"),
        ("div.leadmain > div.bg2 > .row.row3", "副主席"),
        ("div.leadmain > div.bg3 > .row.pdt30", "主席团委员"),
        ("div.leadmain > div.bg3 > .row.pdt10", "书记处书记"),
    )
    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for selector, duty in group_specs:
        group = soup.select_one(selector)
        if group is None:
            raise RuntimeError(f"页面缺少主席团目标分组：{selector}")
        for name_node in group.select(".leadlist > li > .name > a"):
            name = _clean_name(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,12}", name):
                continue
            if name in row_by_name:
                row = row_by_name[name]
                duties = row["duty"].split("、")
                if duty not in duties:
                    row["duty"] = f"{row['duty']}、{duty}"
                    row["evidence"] = row["duty"]
                continue
            row = {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    f"strategy=css；group={selector}；"
                    "name=.leadlist > li > .name > a；"
                    "duty=可见分组标题图片；detail=人物卡无有效href；exclude=bg4新闻区"
                ),
            }
            row_by_name[name] = row
            rows.append(row)
    if not rows:
        raise RuntimeError("主席团与书记处分组未解析出有效姓名")
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
