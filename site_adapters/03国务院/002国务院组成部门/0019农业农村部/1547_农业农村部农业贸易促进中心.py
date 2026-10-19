from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1547",
    "page_type": "职务分组名单页",
    "structure_group": "agri_mczx_current_leader_block_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "grouped_name_list",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".mc2_leader:has(> .mc2_ltit)",
    "name_selector": ".mc2_lcnt > .mc2_ld01.fr > span",
    "duty_selector": ".mc2_lcnt > .mc2_ld01.fl",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "现任领导",
        "end_anchor": "历任领导",
        "include_selectors": [".mc2_leader"],
        "exclude_selectors": [],
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
    "risk_flag": "同页含历任领导分组，只接受标题精确为现任领导的独立区块",
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


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _split_names(value: str) -> list[str]:
    """按页面名单分隔符拆分同一职务下的姓名。"""
    names: list[str] = []
    for part in re.split(r"[、,，；;]", value):
        name = re.sub(r"\s+", "", part)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            names.append(name)
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析标题为“现任领导”的职务分组，排除相邻历任名单。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    current_block = None
    for block in soup.select(".mc2_leader"):
        title_node = block.select_one(".mc2_ltit")
        title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
        if title == "现任领导":
            current_block = block
            break
    if current_block is None:
        raise RuntimeError("页面未找到标题为‘现任领导’的独立分组")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in current_block.select(".mc2_lcnt"):
        duty_node = item.select_one(".mc2_ld01.fl")
        names_node = item.select_one(".mc2_ld01.fr")
        if duty_node is None or names_node is None:
            continue
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True)).rstrip("：:")
        if not duty:
            continue
        for name in _split_names(names_node.get_text(" ", strip=True)):
            if name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": (
                        "strategy=css；leader=.mc2_leader且标题精确为现任领导；"
                        "item=.mc2_lcnt；duty=.mc2_ld01.fl；"
                        "name=.mc2_ld01.fr > span；detail=页面无人物独立链接"
                    ),
                }
            )
    if not rows:
        raise RuntimeError("现任领导分组未解析出有效姓名")
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
