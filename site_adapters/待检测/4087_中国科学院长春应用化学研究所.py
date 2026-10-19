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
    "rule_id": "4087",
    "page_type": "空领导栏目页",
    "structure_group": "ciac_empty_current_leader_page",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "no_extractable_person_data",
    "parser": "page_inline_ciac_empty_current_leader_page",
    "leader_region_selector": "body",
    "risk_flag": "2026-09-20 在线正文仅含栏目标题，未展示任何可验证人物或职务结构",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """拒绝从导航和页脚猜测人物，保持失败记录供后续人工补充入口。"""
    raise RuntimeError("在线领导栏目正文未展示可验证的人物姓名和职务")


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
