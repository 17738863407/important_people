from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3073",
    "page_type": "人物列表完整页",
    "structure_group": "xining_defense_responsible_person_field_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xining_defense_responsible_person_field_v2",
    "leader_region_selector": "#wenzhangzhengwen",
    "name_selector": "负责人姓名字段冒号后文本",
    "duty_selector": "负责人姓名字段原始标签",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "负责人姓名",
        "end_anchor": "办公时间",
        "include_selectors": ["#wenzhangzhengwen"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "官网仅公开负责人姓名字段，未公开具体职务；依据说明保留原始字段标签，不推断职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先上明确隐藏的字段。"""
    for current in [node, *node.parents]:
        if not isinstance(current, Tag):
            continue
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if (
            current.has_attr("hidden")
            or str(current.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide"})
        ):
            return True
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """提取正文中唯一的负责人姓名强字段。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    for paragraph in region.select("p"):
        if _is_hidden(paragraph):
            continue
        text = re.sub(r"[\s\u3000\xa0]+", "", paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"负责人姓名[:：]([\u3400-\u9fff·]{2,5})", text)
        if not match:
            continue
        return [
            {
                "name": match.group(1),
                "duty": "负责人姓名",
                "evidence": "负责人姓名",
                "detail_url": "",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": "#wenzhangzhengwen内负责人姓名字段；冒号后=姓名；原始标签=依据",
            }
        ]
    return []


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
