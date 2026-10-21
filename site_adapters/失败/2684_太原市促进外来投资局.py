from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2684",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_truncated_response_unavailable_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_inline_truncated_response_unavailable_v1",
    "leader_region_selector": "#Zoom",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "当前HTTP 200响应在导航HTML中途截断，正文与#Zoom均未返回，无法验证人物结构",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """页面正文恢复前不输出不可验证的人物记录。"""
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
