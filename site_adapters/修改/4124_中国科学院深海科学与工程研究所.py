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
    "rule_id": "4124",
    "page_type": "leader_page_without_records",
    "structure_group": "S4124",
    "reuse_level": "site_specific",
    "load_mode": "static_html",
    "extraction_mode": "custom",
    "parser": "S001",
    "leader_region_selector": ".content",
    "risk_notes": "2026-09-20 在线页面仅展示“现任领导”栏目标题和附件下载，未公开可验证人员数据。",
    "confidence": "high",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """显式标记当前在线页面未提供人物与现职，不以其他历史页面替代。"""
    raise RuntimeError("在线现任领导页仅显示栏目标题和附件下载，未展示可验证的人物姓名和职务")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
