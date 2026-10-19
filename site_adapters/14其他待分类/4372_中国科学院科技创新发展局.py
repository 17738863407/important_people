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
    "rule_id": "4372",
    "page_type": "机关部门现任领导正文页",
    "structure_group": "cas_department_current_leaders_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cas_bdp_current_leaders_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": ".trs_editor_view p",
    "duty_selector": ".trs_editor_view p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".trs_editor_view"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一职务后可能排列多人，需按原始空白间隔拆分且保留正文顺序",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验现任领导正文段落及职务冒号结构",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".trs_editor_view",
            "name_selector": ".trs_editor_view p",
            "duty_selector": ".trs_editor_view p",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".trs_editor_view"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "现任领导姓名和职务直接呈现在正文HTML中"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_compact_text(value: str) -> str:
    """移除页面为中文对齐插入的空白字符。"""
    return re.sub(r"[\s\u00a0\u2002\u2003\u3000]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文段落顺序解析“职务：姓名列表”。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".trs_editor_view")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        raw_text = paragraph.get_text("", strip=True)
        match = re.match(r"^(.+?)[：:]\s*(.+)$", raw_text)
        if match is None:
            continue
        duty = clean_compact_text(match.group(1))
        raw_names = match.group(2).strip()
        name_parts = re.split(r"[\s\u00a0\u2002\u2003\u3000]{3,}", raw_names)
        for name_part in name_parts:
            name = clean_compact_text(name_part)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".trs_editor_view p中的职务冒号段落",
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
