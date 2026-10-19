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


def clean_text(value: str) -> str:
    """清理网页排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文中的明确“职务：姓名”标题行提取人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".InfoContent")
    if content is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_line in content.get_text("\n", strip=True).splitlines():
        line = clean_text(raw_line)
        match = re.fullmatch(r"([^：:]{2,30})\s*[：:]\s*([\u4e00-\u9fff·]{2,8})", line)
        if match is None:
            continue
        duty, name = clean_text(match.group(1)), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_mzw_duty_name_v2",
                "selector_summary": "scope=.InfoContent；field=完整职务：姓名标题行；detail=none",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1805",
    "page_type": "职务分组名单页",
    "structure_group": "qinghai_mzw_duty_name_lines",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_mzw_duty_name_v2",
    "leader_region_selector": ".InfoContent",
    "name_selector": "职务冒号后姓名",
    "duty_selector": "职务冒号前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".InfoContent"],
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
        "max_detail_links": 0,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".InfoContent",
            "name_selector": "职务冒号后姓名",
            "duty_selector": "职务冒号前文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".InfoContent"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "静态正文已提供明确职务姓名标题行"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
