from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2070",
    "page_type": "人物列表完整页",
    "structure_group": "mof_bill_center_name_space_duty",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "V007_text_name_space_duty_v1",
    "leader_region_selector": ".conabout .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "领导简介为姓名与职务同行文本，限定在唯一 TRS_Editor 正文容器内",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导简介正文中按段落列出的“姓名 职务”记录。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for node in soup.select(".conabout .TRS_Editor p"):
        text = " ".join(node.get_text(" ", strip=True).split())
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>\S.*)", text)
        if not match:
            continue
        records.append({
            "name": match.group("name"),
            "duty": match.group("duty"),
            "evidence": match.group("duty"),
            "detail_url": "",
            "selector_summary": ".conabout .TRS_Editor p：姓名与职务同行",
        })
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
