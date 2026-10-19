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
    "rule_id": "3278",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_health_strong_name_duty_rows",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_health_strong_name_duty_rows_v2",
    "leader_region_selector": ".zfxxgk_zn",
    "name_selector": ".zfxxgk_zn p strong全角空格前文本",
    "duty_selector": ".zfxxgk_zn p strong全角空格后文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个人物strong行",
        "end_anchor": "分工协作说明之前",
        "include_selectors": [".zfxxgk_zn > p > strong"],
        "exclude_selectors": ["strong外职责", "分管段", "联系段", "协作关系", "导航", "页脚"],
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
    "risk_flag": "人物strong后紧跟负责内容并有多段分管、联系和协作说明；只保留strong中全角空格后的原始职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfxxgk_zn",
            "name_selector": "p strong全角空格前文本",
            "duty_selector": "p strong全角空格后文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个人物strong行",
                "end_anchor": "分工协作说明之前",
                "include_selectors": [".zfxxgk_zn > p > strong"],
                "exclude_selectors": ["strong外职责", "分管段", "联系段", "协作关系", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML strong字段直接提供姓名和职务"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "zfxxgk_zn" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zfxxgk_zn")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in region.select("p strong"):
        if _is_hidden(node):
            continue
        parts = re.split(r"\u3000+", node.get_text("", strip=True), maxsplit=1)
        if len(parts) != 2:
            continue
        name = re.sub(r"\s+", "", _clean_text(parts[0]))
        duty = _clean_text(parts[1]).strip(" ：:，,。.；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_health_strong_name_duty_rows_v2",
                "selector_summary": ".zfxxgk_zn p strong；全角空格前姓名；后部完整职务",
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
