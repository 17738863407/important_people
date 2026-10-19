from __future__ import annotations

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
    "rule_id": "3541",
    "page_type": "管理团队公开空页面",
    "structure_group": "csgc_empty_management_team_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".gltd-module-content",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "管理团队",
        "end_anchor": "",
        "include_selectors": [".gltd-module-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "官方管理团队正文当前明确显示暂时没有信息",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """确认管理团队专属正文当前明确为空。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".gltd-module-content")
    if scope is None:
        raise ValueError("未找到管理团队正文容器，页面结构可能已变更")
    if "暂时没有信息" not in scope.get_text(" ", strip=True):
        raise ValueError("管理团队正文已不再为空，需要重新设计人物解析规则")
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
