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
    "rule_id": "4083",
    "page_type": "领导卡片页",
    "structure_group": "sia_leader_strong_p_card",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "V001_css_field_pair_v1",
    "leader_region_selector": "li.col-md-4.col-sm-6",
    "name_selector": "h4 strong",
    "duty_selector": ".tj p",
    "risk_flag": "页面领导卡片无可验证独立详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


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
