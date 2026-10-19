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
    "rule_id": "3438",
    "page_type": "机构领导分类空列表",
    "structure_group": "changchun_govinfo_empty_subcat",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "inline_parse_page",
    "leader_region_selector": "a#c_2421",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "机构领导",
        "end_anchor": "",
        "include_selectors": ["a#c_2421", "ul#result-body"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "机构领导分类当前公开JSONP接口返回零条记录",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """公开入口仅提供机构领导分类锚点，当前分类接口没有人物记录。"""
    if 'id="c_2421"' not in html or "机构领导" not in html:
        raise ValueError("未找到机构领导分类锚点，页面结构可能已变更")
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
