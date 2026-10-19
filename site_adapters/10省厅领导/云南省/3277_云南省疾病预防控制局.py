from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3277",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_disease_control_strong_fields",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_disease_control_strong_fields_v2",
    "leader_region_selector": ".zw-article",
    "name_selector": ".zw-article p strong:first-child",
    "duty_selector": ".zw-article p strong:not(:first-child)",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个人物strong字段段",
        "end_anchor": "末个人物分管段",
        "include_selectors": [".zw-article > p"],
        "exclude_selectors": ["strong外职责", "分管段", "导航", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "人物段strong后还有负责内容，后续段为分管内容；只拼接姓名之后的strong职务字段，不替换机构简称",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zw-article",
            "name_selector": "p strong:first-child",
            "duty_selector": "p strong:not(:first-child)",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个人物strong字段段",
                "end_anchor": "末个人物分管段",
                "include_selectors": [".zw-article > p"],
                "exclude_selectors": ["strong外职责", "分管段", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML人物段strong字段直接提供姓名和完整职务"},
    },
}


def _clean_text(value: str) -> str:
    return "".join(
        str(value or "")
        .replace("\u2002", " ")
        .replace("\u2003", " ")
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .split()
    )


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "zw-article" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zw-article")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        if _is_hidden(paragraph):
            continue
        strong_nodes = paragraph.select("strong")
        if len(strong_nodes) < 2:
            continue
        name = _clean_text(strong_nodes[0].get_text("", strip=True))
        duty = "".join(_clean_text(node.get_text("", strip=True)) for node in strong_nodes[1:])
        duty = duty.strip(" ：:，,。.；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_disease_control_strong_fields_v2",
                "selector_summary": ".zw-article人物p；首个strong姓名；其余strong完整职务",
            }
        )
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
