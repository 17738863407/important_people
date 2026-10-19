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
    "rule_id": "3658",
    "page_type": "分区职务名单页",
    "structure_group": "hzau_current_leader_sections_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hzau_current_leader_sections_v1",
    "leader_region_selector": ".Leader_Div",
    "name_selector": ".Leader_Line_Content a",
    "duty_selector": ".Leader_Line_head, .Leader_Title_Div",
    "detail_link_selector": "",
    "content_scope": {"include_selectors": [".Leader_Div"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "党委常委职务来自区段标题；全部人物链接均为JavaScript占位",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除全角、不间断及普通排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按区段及行顺序提取人物，并按首次出现顺序聚合现任职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".Leader_Div")
    if region is None:
        return []
    people: dict[str, list[str]] = {}
    for section in region.select(":scope > .Leader_Content_Div"):
        title_node = section.find_previous_sibling(class_="Leader_Title_Div")
        section_title = _clean_text(title_node.get_text(" ", strip=True)) if title_node is not None else ""
        for group in section.select(":scope > .Leader_Line"):
            duty_node = group.select_one(":scope > .Leader_Line_head")
            duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else section_title
            if not duty or duty in {"党委领导", "行政领导"}:
                continue
            for anchor in group.select(".Leader_Line_Content a"):
                name = _clean_text(anchor.get_text(" ", strip=True))
                if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                    duties = people.setdefault(name, [])
                    if duty not in duties:
                        duties.append(duty)

    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(duties), detail_url="", evidence="；".join(duties),
            confidence="high", parser=page_rule["parser"],
            selector_summary=".Leader_Div各区段的.Leader_Line_head或区段标题 + .Leader_Line_Content a",
        )
        for name, duties in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
