from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4214",
    "page_type": "国务院发展研究中心直属单位详情页",
    "structure_group": "drc_department_leader_block",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "page_inline_drc_department_leader_block_v1",
    "leader_region_selector": "#MainContent_personleaderdiv",
    "name_selector": ".leadername1, .leadername2, a",
    "duty_selector": "#MainContent_personleaderh4",
    "detail_link_selector": "#MainContent_personleaderdiv a[href]",
    "detail_strategy": {"required": False, "mode": "same_block_link"},
    "risk_flag": "正文含历史顾问、学术指导及旧编委名单，部门人员块亦不等于领导；仅允许解析官方部门领导专属容器。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """只解析官网明确标记的部门领导容器，空容器按失败处理。"""
    from bs4 import BeautifulSoup, Tag
    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#MainContent_personleaderdiv")
    if not isinstance(region, Tag):
        raise RuntimeError("官网未提供部门领导专属容器")

    rows: list[dict] = []
    seen: set[str] = set()
    for node in region.select(".leadername1, .leadername2, a"):
        name = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        seen.add(name)
        href = node.get("href", "") if isinstance(node, Tag) else ""
        rows.append(
            {
                "name": name,
                "duty": "部门领导",
                "evidence": "部门领导",
                "detail_url": urljoin(final_url, href) if href else "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "scope=#MainContent_personleaderdiv；exclude=正文历史名单和部门人员块",
            }
        )
    if not rows:
        raise RuntimeError("官网部门领导专属容器当前为空；部门人员块仅有姓名且无领导职务证据")
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
